# -*- coding: utf-8 -*-
import os
import time
import shutil
import unittest
from configparser import ConfigParser

from kb_eukrep.kb_eukrepImpl import kb_eukrep
from kb_eukrep.kb_eukrepServer import MethodContext
from kb_eukrep.authclient import KBaseAuth as KBaseAuth

from kb_eukrep.Utils.EukrepUtil import EukrepUtil


from installed_clients.AssemblyUtilClient import AssemblyUtil
from installed_clients.DataFileUtilClient import DataFileUtil
from installed_clients.WorkspaceClient import Workspace


class kb_eukrepTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # token = os.environ.get('KB_AUTH_TOKEN', None)
        cls.token = os.environ.get('KB_AUTH_TOKEN', None)
        config_file = os.environ.get('KB_DEPLOYMENT_CONFIG', None)
        cls.cfg = {}
        config = ConfigParser()
        config.read(config_file)
        for nameval in config.items('kb_eukrep'):
            cls.cfg[nameval[0]] = nameval[1]
        # Getting username from Auth profile for token
        authServiceUrl = cls.cfg['auth-service-url']
        auth_client = KBaseAuth(authServiceUrl)
        user_id = auth_client.get_user(cls.token)
        # WARNING: don't call any logging methods on the context object,
        # it'll result in a NoneType error
        cls.ctx = MethodContext(None)
        cls.ctx.update({'token': cls.token,
                        'user_id': user_id,
                        'provenance': [
                            {'service': 'kb_eukrep',
                             'method': 'please_never_use_it_in_production',
                             'method_params': []
                             }],
                        'authenticated': 1})
        cls.wsURL = cls.cfg['workspace-url']
        cls.wsClient = Workspace(cls.wsURL)
        cls.serviceImpl = kb_eukrep(cls.cfg)
        cls.scratch = cls.cfg['scratch']
        cls.callback_url = os.environ['SDK_CALLBACK_URL']
        suffix = int(time.time() * 1000)
        cls.wsName = "test_kb_eukrep_" + str(suffix)
        # ret = cls.wsClient.create_workspace({'workspace': cls.wsName})  # noqa

        cls.ws_info = cls.wsClient.create_workspace({'workspace': cls.wsName})  # noqa
        cls.dfu = DataFileUtil(os.environ['SDK_CALLBACK_URL'], token=cls.token)
        cls.au = AssemblyUtil(os.environ['SDK_CALLBACK_URL'], token=cls.token)
        cls.eukrep_runner = EukrepUtil(cls.cfg)
        cls.prepare_data()


    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'wsName'):
            cls.wsClient.delete_workspace({'workspace': cls.wsName})
            print('Test workspace was deleted')

    # NOTE: According to Python unittest naming rules test method names should start from 'test'. # noqa

    @classmethod
    def prepare_data(cls):
        """
        Lets put everything on workspace
        """
        #
        # building Assembly
        #
        assembly_filename1 = '3300037410_eukrep_test.fna'
        cls.assembly_filename_path1 = os.path.join(cls.scratch, assembly_filename1)
        shutil.copy(os.path.join("data", assembly_filename1), cls.assembly_filename_path1)

        # from scratch upload to workspace
        assembly_params1 = {
            'file': {'path': cls.assembly_filename_path1},
            'workspace_name': cls.ws_info[1],
            'assembly_name': 'MyAssembly1'
        }

        # puts assembly object onto shock
        cls.assembly_ref1 = cls.au.save_assembly_from_fasta(assembly_params1)

    def getWsClient(self):
        return self.__class__.wsClient

    def getWsName(self):
        return self.ws_info[1]

    def getImpl(self):
        return self.__class__.serviceImpl

    def getContext(self):
        return self.__class__.ctx

    def test_run_eukrep_default(self):
        method_name = 'test_run_eukrep_default'
        print ("\n=================================================================")
        print ("RUNNING "+method_name+"()")
        print ("=================================================================\n")

        # eukrep should run to completion here
        ret = self.getImpl().run_kb_eukrep(self.getContext(),
                                            {'workspace_name': self.getWsName(),
                                             'assembly_ref': self.assembly_ref1,
                                             'output_assembly_name': 'test.assembly' })
