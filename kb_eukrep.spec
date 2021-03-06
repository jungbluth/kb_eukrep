/*
A KBase module: kb_eukrep
*/

module kb_eukrep {

    /* A boolean - 0 for false, 1 for true.
        @range (0, 1)
    */
    typedef int boolean;

    /* An X/Y/Z style reference
    */
    typedef string obj_ref;

    /*
        required params:
        assembly_ref: Genome assembly object
        workspace_name: the name of the workspace it gets saved to.

    */
    typedef structure {
        obj_ref assembly_ref;
        string workspace_name;
        string output_assembly_name;

    } eukrepInputParams;

    /*
        result_directory: folder path that holds all files generated by run_kb_eukrep
        report_name: report name generated by KBaseReport
        report_ref: report reference generated by KBaseReport
    */
    typedef structure{
        string result_directory;
        obj_ref assembly_obj_ref;
        string report_name;
        string report_ref;
    }eukrepResult;

    funcdef run_kb_eukrep(eukrepInputParams params)
        returns (eukrepResult returnVal) authentication required;

};
