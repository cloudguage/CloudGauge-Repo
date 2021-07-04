import xml.etree.ElementTree as ET
import time
def update_jmx(params):
    try:
        path=params['jmeter_bin_path']+"/examples/"
        tree = ET.parse(params['JmxFile'])
        root = tree.getroot()
        config_type=params['JmxFile'].split('.')[0]
        for elem in root.iter():
            item=elem.attrib
            #Threads,RampupPeriod,LoopCount common for all resources
            if 'ThreadGroup.num_threads' in item.values():
                elem.text=str(params['NoOfThreads'])
            if 'ThreadGroup.ramp_time' in item.values():
                elem.text=str(params['RampUpPeriod'])
            if 'LoopController.loops' in item.values():
                elem.text=str(params['LoopCount'])
            if 'ThreadGroup.duration' in item.values():
                elem.text=str(params['TimeOut'])
            #SqlDB's
            if config_type.__contains__("SQLDB") or config_type.__contains__("RDS") or config_type.__contains__("DB2"):
                if 'dbUrl' in item.values():
                    elem.text=str(params['ConnectionString'])
                if 'query' in item.values():
                    elem.text=str(params['query'])
                if config_type.__contains__("DB2-Query"):
                    if 'username' in item.values():
                        elem.text=str(params['user_name'])
                    if 'password' in item.values():
                        elem.text=str(params['password'])
            #NoSqlDB's       
            if config_type.__contains__("CosmosDB") or config_type.__contains__("FireStore") or config_type.__contains__("BigQuery") or config_type.__contains__("DynamoDB") or config_type.__contains__("Cloudant"):
                    if 'SystemSampler.directory' in item.values():
                        elem.text=params['jmeter_bin_path']+"/examples"
                    if 'Argument.value' in item.values():
                        elem.text=params['new_script_name']
            #CloudFunctions         
            if config_type.__contains__("Function"):
                if 'HTTPSampler.domain' in item.values():
                    elem.text=str(params['sampler_domain'])
                if 'HTTPSampler.path' in item.values():
                    elem.text=str(params['sampler_path'])
                if params['Parameter1']:
                    if 'filename' in item.values():
                        if elem.text=="#CSV_FILE#":
                            elem.text=str(params['filename'])
                else:
                    #if no parameter is given disable CSVDataConfig and HeaderManager element in jmeter
                    if elem.text=="#CSV_FILE#":
                        elem.text=""
                    if 'Argument.value' in item.values():
                        elem.text=""
                    csv_elem=elem.find("CSVDataSet")
                    if csv_elem:
                        csv_elem.set('enabled','false')
                    header_manager_elem=elem.find("HeaderManager")
                    if header_manager_elem:
                        header_manager_elem.set('enabled','false')
                        
            if config_type.__contains__("Azure-WebApp") or config_type.__contains__("AWS-WebApp") or  config_type.__contains__("IBM-WebApp"):
                if 'HTTPSampler.domain' in item.values():
                    elem.text=str(params['sampler_domain'])
                if params['Parameter1']:     
                    if 'HTTPSampler.path' in item.values():
                        elem.text=str(params['sampler_path'])
                        
            if config_type.__contains__("GCP-WebApp"):
                if 'HTTPSampler.path' in item.values():
                    elem.text=str(params['sampler_path'])
                    

                        
        tree.write(path+params['duplicate_file_name'],encoding='UTF-8',xml_declaration=True)
        print("xml for "+params['InstanceHead']+" created at"+time.strftime("%d%b%Y-%Hh-%Mm"))
    except Exception as e:
        print(e)
