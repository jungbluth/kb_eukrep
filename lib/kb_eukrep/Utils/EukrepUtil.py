import errno
import json
import os
import subprocess
import sys
import time
import uuid
import zipfile
import copy
import shutil
import math

from installed_clients.AssemblyUtilClient import AssemblyUtil
from installed_clients.DataFileUtilClient import DataFileUtil
from installed_clients.KBaseReportClient import KBaseReport

from shutil import copyfile


# for future expansion
# from kb_eukrep.BinningUtilities import BinningUtil as bu


def log(message, prefix_newline=False):
    """Logging function, provides a hook to suppress or redirect log messages."""
    print(('\n' if prefix_newline else '') + '{0:.2f}'.format(time.time()) + ': ' + str(message))


class EukrepUtil:
    EUKREP_BASE_PATH = '/Eukrep'
    EUKREP_RESULT_DIRECTORY = 'eukrep_output_dir'
    MAPPING_THREADS = 16
    BBMAP_MEM = '30g'

    def __init__(self, config):
        self.callback_url = config['SDK_CALLBACK_URL']
        self.scratch = config['scratch']
        self.shock_url = config['shock-url']
        self.ws_url = config['workspace-url']
        self.dfu = DataFileUtil(self.callback_url)
        self.au = AssemblyUtil(self.callback_url)

    def _validate_run_eukrep_params(self, task_params):
        """
        _validate_run_eukrep_params:
                validates params passed to run_eukrep method
        """
        log('Start validating run_eukrep params')

        # check for required parameters
        for p in ['assembly_ref', 'workspace_name']:
            if p not in task_params:
                raise ValueError('"{}" parameter is required, but missing'.format(p))

    def _mkdir_p(self, path):
        """
        _mkdir_p: make directory for given path
        """
        if not path:
            return
        try:
            os.makedirs(path)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise

    def _run_command(self, command):
        """
        _run_command: run command and print result
        """
        os.chdir(self.scratch)
        log('Start executing command:\n{}'.format(command))
        log('Command is running from:\n{}'.format(self.scratch))
        pipe = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        output, stderr = pipe.communicate()
        exitCode = pipe.returncode

        if (exitCode == 0):
            log('Executed command:\n{}\n'.format(command) +
                'Exit Code: {}\n'.format(exitCode))
        else:
            error_msg = 'Error running command:\n{}\n'.format(command)
            error_msg += 'Exit Code: {}\nOutput:\n{}\nStderr:\n{}'.format(exitCode, output, stderr)
            raise ValueError(error_msg)
            sys.exit(1)
        return (output, stderr)

    def _get_contig_file(self, assembly_ref):
        """
        _get_contig_file: get contig file from GenomeAssembly object
        """
        contig_file = self.au.get_assembly_as_fasta({'ref': assembly_ref}).get('path')

        sys.stdout.flush()
        contig_file = self.dfu.unpack_file({'file_path': contig_file})['file_path']

        return contig_file

    def retrieve_assembly(self, task_params):
        if os.path.exists(task_params['contig_file_path']):
            assembly = task_params['contig_file_path']
            print("FOUND ASSEMBLY ON LOCAL SCRATCH")
        else:
            # we are on njsw so lets copy it over to scratch
            assembly = self._get_contig_file(task_params['assembly_ref'])
        return assembly


    def generate_eukrep_command(self, assembly_ref, euk_output_assembly_ref, noneuk_output_assembly_ref):
        """
        generate_command: eukrep
        """

        log("\n\nRunning generate_jorg_command")
        command = 'EukRep '
        command += '-i {} '.format(assembly_ref)
        command += '-o {} '.format(euk_output_assembly_ref)
        command += '--prokarya {} '.format(noneuk_output_assembly_ref)
        log('Generated eukrep command: {}'.format(command))

        return command


    def generate_html_report(self):
        """
        generate_html_report: generate html summary report
        """

        log('Start generating html report')
        #html_report = list()

        output_directory = os.path.join(self.scratch, 'html_dir_' + str(uuid.uuid4()))
        self._mkdir_p(output_directory)
        result_file_path = os.path.join(output_directory, 'report.html')

        # get summary data from existing assembly object and bins_objects
        Summary_Table_Content = ''
        Overview_Content = ''

        # generate overview content

        # Example
        # Overview_Content += '<p>Input contigs: {}</p>'.format(input_contig_count)

        Overview_Content += '<p>Iteration Selected: 3</p>'
        Overview_Content += '<p>Number of contigs: 4</p>'
        Overview_Content += '<p>Circularized genome: No </p>'

        with open(result_file_path, 'w') as result_file:
            with open(os.path.join(os.path.dirname(__file__), 'report_template.html'),
                      'r') as report_template_file:
                report_template = report_template_file.read()
                report_template = report_template.replace('<p>Overview_Content</p>',
                                                          Overview_Content)
                report_template = report_template.replace('Summary_Table_Content',
                                                          Summary_Table_Content)
                result_file.write(report_template)

        # save html dir to shock
        def dir_to_shock(dir_path, name, description):
            '''
            For regular directories or html directories

            name - for regular directories: the name of the flat (zip) file returned to ui
                   for html directories: the name of the html file
            '''
            dfu_fileToShock_ret = self.dfu.file_to_shock({
                'file_path': dir_path,
                'make_handle': 0,
                'pack': 'zip',
                })

            dir_shockInfo = {
                'shock_id': dfu_fileToShock_ret['shock_id'],
                'name': name,
                'description': description
                }

            return dir_shockInfo

        html_shockInfo = dir_to_shock(output_directory, 'report.html', 'HTML report for Eukrep')

        """
        html_report.append({'path': result_file_path,
                            'name': os.path.basename(result_file_path),
                            'label': os.path.basename(result_file_path),
                            'description': 'HTML summary report for kb_concoct App'})

        return html_report
        """

        return [html_shockInfo]

    def generate_report(self, params):
        """
        generate_report: generate summary report

        """
        log('Generating report')

        output_html_files = self.generate_html_report()

        report_params = {
              'message': '',
              'workspace_name': params.get('workspace_name'),
              'html_links': output_html_files,
              'direct_html_link_index': 0,
              'html_window_height': 500,
              'report_object_name': 'kb_eukrep_report_' + str(uuid.uuid4())}

        kbase_report_client = KBaseReport(self.callback_url)
        output = kbase_report_client.create_extended_report(report_params)

        report_output = {'report_name': output['name'], 'report_ref': output['ref']}

        return report_output

    def run_eukrep(self, task_params):
        """
        run_eukrep: eukrep app

        required params:
            assembly_ref: Metagenome assembly object reference
            binned_contig_name: BinnedContig object name and output file header
            workspace_name: the name of the workspace it gets saved to.
            reads_file: list of reads object (PairedEndLibrary/SingleEndLibrary)
            upon which EUKREP will be run

        optional params:
            TBD

            ref: https://github.com/BinPro/EUKREP/blob/develop/README.md
        """
        log('--->\nrunning EukrepUtil.run_eukrep\n' +
            'task_params:\n{}'.format(json.dumps(task_params, indent=1)))

        self._validate_run_eukrep_params(task_params)

        # get assembly
        contig_file = self._get_contig_file(task_params['assembly_ref'])
        task_params['contig_file_path'] = contig_file

        # clean the assembly file so that there are no spaces in the fasta headers
        assembly = self.retrieve_assembly(task_params)
        task_params['contig_file_path'] = assembly


        assembly_ref = task_params['contig_file_path']
        euk_output_assembly_ref = assembly_ref.rsplit('.', 1)[0] + "_eukaryote.fna"
        noneuk_output_assembly_ref = assembly_ref.rsplit('.', 1)[0] + "_noneukaryote.fna"

        command = self.generate_eukrep_command(assembly_ref, euk_output_assembly_ref, noneuk_output_assembly_ref)
        self._run_command(command)

        dest = os.path.abspath(self.scratch)

        euk_output_assembly_ref = os.path.basename(euk_output_assembly_ref)
        noneuk_output_assembly_ref = os.path.basename(noneuk_output_assembly_ref)

        log("assembly_ref is {}".format(assembly_ref))
        log("euk_output_assembly_ref is {}".format(euk_output_assembly_ref))
        log("noneuk_output_assembly_ref is {}".format(noneuk_output_assembly_ref))

        euk_output_assembly_ref_object = self.au.save_assembly_from_fasta(
            {'file': {'path': dest + '/' + euk_output_assembly_ref},
             'workspace_name': task_params['workspace_name'],
             'assembly_name': euk_output_assembly_ref
             })

        noneuk_output_assembly_ref_object = self.au.save_assembly_from_fasta(
            {'file': {'path': dest + '/' + noneuk_output_assembly_ref},
             'workspace_name': task_params['workspace_name'],
             'assembly_name': noneuk_output_assembly_ref
             })

        # generate report
        reportVal = self.generate_report(task_params)
        returnVal = {
            'euk_output_assembly_ref': euk_output_assembly_ref_object,
            'noneuk_output_assembly_ref': noneuk_output_assembly_ref_object
        }
        returnVal.update(reportVal)
        #
        return reportVal
