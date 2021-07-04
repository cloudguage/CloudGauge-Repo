import logging
import subprocess
import os
import time
from subprocess import Popen
from subprocess import PIPE
import io
import json
import shutil
import xml.etree.ElementTree as ET
import datetime
from JmeterLib import *
from http.server import BaseHTTPRequestHandler, HTTPServer
import time


def run_jmeter(params):
    # Input file: Copy of Master File (.JMX format)
    # Output file: Jmeter report to be created (.CSV format)
    input_file_name=params['duplicate_file_name']
    output_file_name=input_file_name.replace('.jmx','.csv')
    try:
        command="jmeter -n -t examples/"+input_file_name+" -l examples/"+output_file_name
        jmeter_command=Popen(command,shell=True ,stdout=subprocess.PIPE, cwd=params['jmeter_bin_path'])
        status=jmeter_command.communicate()[0]
        encoding = 'utf-8'
        result=status.decode(encoding)
        if result.__contains__("summary"):
            result=result.split('\n')
            for item in result:
                #Taking the cummulative summary, ignoring the incremental summary
                if item.__contains__("summary ="):
                    output=item
                    print(output)
                    break
            output=output.replace("     ",'').replace("  ",'').replace(" =","=").replace(": ",":").split('/s')
            #no_of_threads=output[0].split('in')[0].split('=')[1]
            params['AverageTime']=output[1].split(' ')[1].split(':')[1]+"ms"
            params['MinTime']=output[1].split(' ')[2].split(':')[1]+"ms"
            params['MaxTime']=output[1].split(' ')[3].split(':')[1]+"ms"
            errors=int(output[1].split(' ')[-2].split(':')[1])
            return errors
        else:
            log_error(params,"Failed to run jmeter")
            return
    except Exception as e:
        print(e)
        log_error(params,"Failed to run jmeter")
        return
    
    
def execute_performance(params):
    #Function to execute performance of a test case
    #Step1: create a duplicate file of master jmx
    #Step2: update_jmx()-update the dupllicate file with test case configuration
    #Step3: Run jmeter
    #Step4: Upload the jmeter result (.csv file) to Output folder
    #Step5: Update the Test Cases output sheet of runs instance
    print("Running: "+params['ConfigType'])
    try:
        #Source:Master Jmx file present in current project folder
        #Destination: Copy of Master Jmx created in Jmeter's bin/examples folder
        #flag for Devops
        flag=0
        source=params['JmxFile']
        destination=params['jmeter_bin_path']+"/examples/"+params['duplicate_file_name']
        shutil.copy(source,destination)
        #update_jmx() function is present in JmeterLib package
        update_jmx(params)
        jmeter_result=run_jmeter(params)
        if jmeter_result is not None:
            errors=jmeter_result
            params['MaxThreadsExecuted']=int(params['NoOfThreads'])*int(params['LoopCount'])-errors
            if errors==0:
                print("Jmeter Result: "+"Pass")
                params['PassOrFail']="Pass"
                flag=1
            else:
                print("Jmeter Result: "+"Fail")
                params['PassOrFail']="Fail"
            #Output file with same name with .csv extension will be created at same destination
            output_file_path=destination.replace(".jmx",".csv")
            output_file_name=output_file_path.split('/')[-1]
            output_files_folder_id=get_file_id_for_master_file(credentials,master_configuration['id'],"JmeterLogs")
            uploaded_file_id=upload_output_file(credentials,output_file_name,output_file_path,output_files_folder_id)
            if uploaded_file_id is not None:
                params['ReportFile']="https://drive.google.com/file/d/"+uploaded_file_id
                update_sheet(params)
        return flag
    except Exception as e:
        log_error(params,"Failed to execute performance"+str(e))
        return 0


def run_command(command):
    #Function tu run CLI commands with Popen
    status=Popen(command,shell=True ,stdout=subprocess.PIPE)
    output=status.communicate()[0]
    encoding = 'utf-8'
    decoded_output = output.decode(encoding)
    try:
        json_file=json.loads(decoded_output)
        return json_file
    except:
        return decoded_output





#Azure Cloud Resources

def azure_function_execute(params):
    download_file_from_parent_folder(credentials,jmeter_resources_folder_id,params['JmxFile'])
    try:
        az_function_command="az functionapp list"
        #Execute CLI command on the Cloud to retrieve meta data of the App Service
        json_file=run_command(az_function_command)
        #InstanceHead: FunctionAppName
        for val in json_file:
            if val.get('name')==params['InstanceHead']:
                function_url=val.get('hostNames')[0]    
                params['sampler_domain']=function_url.replace('https://','')
                #Parameter1: CSVFile
                if params['Parameter1']:
                    csv_file=eval(params['Parameter1'])['CsvFileName']
                    download_status=download_file_from_parent_folder(credentials,parameter_files_folder_id,csv_file)
                    if download_status:
                        params['filename']=os.getcwd()+"\\"+csv_file
                    else:
                        log_error("Failed to download parameter file for  "+params['InstanceHead'])
                #InstanceDetail: FunctionName
                params['sampler_path']="api/"+params['InstanceDetail']
                params['Location']=val['location']
                params['duplicate_file_name']=get_duplicate_file_name(params)
                #Now, since we have all the data execute JMeter Template and capture the parallel running results
                res=execute_performance(params)
                return res
        #if FunctionAPP not found or is not in runnig state
        log_error(params,"Function not found or it's not in running state")
        return 0
    except Exception as e:
        log_error(params,"An Error Occured: "+str(e))
        return 0


def azure_webapp_connect(params):
    download_file_from_parent_folder(credentials,jmeter_resources_folder_id,params['JmxFile'])
    try:
        command="az webapp list"
        #Execute CLI command on the Cloud to retrieve meta data of the App Service
        json_file=run_command(command)
        for val in json_file:
            if val['name']==params['InstanceHead']:
                params['sampler_domain']=val['hostNames'][0]
                params['sampler_path']=None
                if params['Parameter1']:
                    #Parameter1 : String representation of dictionary ex:{"LandingPage":"Home/Index"}
                    landing_page=eval(params['Parameter1'])['LandingPage']
                    params['sampler_path']=landing_page
                params['Location']=val['location']
                params['duplicate_file_name']=get_duplicate_file_name(params)
                #Now, since we have all the data execute JMeter Template and capture the parallel running results
                res=execute_performance(params)
                return res
        log_error(params,"Web app not found or not in running state.")
        return 0
    except Exception as e:
        log_error(params,"An Error Occured: "+str(e))
        return 0
    
def azure_sqldb_query(params):
    #Dowloading the master jmx file
    download_file_from_parent_folder(credentials,jmeter_resources_folder_id,params['JmxFile'])
    try:
        if params['ConnectionString']=='':
            if params['ServerName'] and params['UserName'] and params['Password']:
                #If InstanceHead is of server.db format
                if params['InstanceHead'].__contains__('.'):
                    params['InstanceHead']=params['InstanceHead'].split('.')[1]
                sql_conn_str_command="az sql db show-connection-string  --client jdbc --server "+params['ServerName']+" --name "+params['InstanceHead']
                #Execute CLI command on the Cloud to retrieve meta data of the App Service
                command_output=run_command(sql_conn_str_command)
                if command_output:
                    params['ConnectionString']=command_output
                    #UserName and Passsword are encrypted
                    params['ConnectionString']=params['ConnectionString'].replace("<username>",params['UserName'])
                    params['ConnectionString']=params['ConnectionString'].replace("<password>",params['Password'])
                else:
                    log_error(params,"ResourceNotFound or invalid Connection/TestCase input given.")
                    return 0
            else:
                log_error(params,"Required connection parameters are missing.")
                return 0
        #InstanceDetail: Table Name
        #Parameter2: RecordsLimit
        #default records limit: 100
        records_limit=100
        if params['Parameter1']:    
            records_limit=eval(params['Parameter1'])['RecordsLimit']
        az_show_command="az sql db show --resource-group "+params['ResourceGroup']+" --server "+params['ServerName']+" --name "+params['InstanceHead']
        az_show_command_op=run_command(az_show_command)
        params['Location']=az_show_command_op['location']
        params['query']="select TOP("+str(records_limit)+") * from "+params['InstanceDetail']
        params['duplicate_file_name']=get_duplicate_file_name(params)
        #Now, since we have all the data execute JMeter Template and capture the parallel running results
        res=execute_performance(params)
        return res
    except Exception as e:
        log_error(params,"An Error Occured: "+str(e))
        return 0

#GCP
def firestore_python_update(params):
    #Function to update python script with test case configuration
    #Step1:Taking initial python script which is a text file, creating a new file with required configuration
    #Step2:Change the extension from .txt to .py
    download_file_from_parent_folder(credentials,jmeter_resources_folder_id,"GCP-FireStore-Query.txt")
    try:
        python_file=open("GCP-Firestore-Query.txt","r")
        data=python_file.read()
        python_file.close()
        new_data1=data.replace("#SERVICE_ACCOUNT_KEY_PATH#",params['service_account_key_path'])
        new_data2=new_data1.replace("#COLLECTION_NAME#",params['InstanceHead'])
        #default records limit: 100
        records_limit=100
        if params['Parameter1']:    
            records_limit=eval(params['Parameter1'])['RecordsLimit']
        new_data3=new_data2.replace("#LIMIT#",str(records_limit))
        new_script_name=get_duplicate_file_name(params,".txt")
        python_file2=open(params['jmeter_bin_path']+"/examples/"+new_script_name,"w")
        python_file2.write(new_data3)
        python_file2.close()
        params['new_script_name']=new_script_name.replace(".txt",".py")
        change_file_extension(params['jmeter_bin_path']+"/examples/"+new_script_name,".py")
    except Exception as e:
        log_error(params,"Failed to update python script")


def gcp_firestore_query(params):
    download_file_from_parent_folder(credentials,jmeter_resources_folder_id,params['JmxFile'])
    try:
        #ServiAccountKey should be present in CWD
        if os.path.exists("GCloudServiceAccountKey.json"):
            params['service_account_key_path']=os.getcwd()+"\GCloudServiceAccountKey.json"
            params['duplicate_file_name']=get_duplicate_file_name(params)
            firestore_python_update(params)
            #Now, since we have all the data execute JMeter Template and capture the parallel running results
            res=execute_performance(params)
            return res
        else:
            log_error(params,"No service account key found")
            return 0
    except Exception as e:
        log_error(params,"An Error Occured: "+str(e))



 #AWS
 
def aws_rds_query(params):
    download_file_from_parent_folder(credentials,jmeter_resources_folder_id,params['JmxFile'])
    try:
        if params['ConnectionString']=='':
            params['ConnectionString']="jdbc:postgresql://"+params['ServerPath']+":"+str(params['Port'])+"/"+params['InstanceHead']
        #InstanceDetail: Table Name
        #Parameter1:RecordsLimit
        if params['Parameter1']:    
            records_limit=eval(params['Parameter1'])['RecordsLimit']
        params['query']="select * from "+params['InstanceDetail']+" LIMIT "+str(records_limit)+";"
        params['duplicate_file_name']=get_duplicate_file_name(params)
        #Now, since we have all the data execute JMeter Template and capture the parallel running results
        res=execute_performance(params)
        return res
    except Exception as e:
        log_error(params,"An Error Occured: "+str(e))
        return 0


#IBM
def ibm_db2_query(params):
    download_file_from_parent_folder(credentials,jmeter_resources_folder_id,params['JmxFile'])
    try:
        command="ibmcloud resource service-key "+"\""+params['ServiceKeyName']+"\""+" --output json"
        #Execute CLI command on the Cloud to retrieve meta data of the App Service
        json_file=run_command(command)
        params['ConnectionString']=json_file[0]['credentials']['jdbcurl']
        params['user_name']=json_file[0]['credentials']['username']
        params['password']=json_file[0]['credentials']['password']
        if params['Parameter1']:    
            records_limit=eval(params['Parameter1'])['RecordsLimit']
        params['query']="select * from "+params['InstanceHead']+" LIMIT "+str(records_limit)
        params['duplicate_file_name']=get_duplicate_file_name(params)
        #Now, since we have all the data execute JMeter Template and capture the parallel running results
        res=execute_performance(params)
        return res
    except Exception as e:
        log_error(params,"An Error Occured: "+str(e))
        return 0
        
        

def get_test_cases_params(df,index):
    params={}
    params['ConfigType']=df['ConfigType'][index]
    params['JmxFile']=df['JmxFile'][index]
    params['SubscriptionFriendlyName']=df['SubscriptionFriendlyName'][index]
    params['ConnectionProfile']=df['ConnectionProfile'][index]
    params['ResourceFriendlyName']=df['ResourceFriendlyName'][index]
    params['IsScope']=df['IsScope'][index]
    params['InstanceHead']=df['InstanceHead'][index]
    params['InstanceDetail']=df['InstanceDetail'][index]
    params['Parameter1']=df['Parameter1'][index]
    params['Parameter2']=df['Parameter2'][index]
    params['NoOfThreads']=df['NoOfThreads'][index]
    params['RampUpPeriod']=df['RampUpPeriod'][index]
    params['TimeOut']=df['TimeOut'][index]
    params['LoopCount']=df['LoopCount'][index]
    params['jmeter_bin_path']="C:/Users/servicemeshadmin/Desktop/jmeter/jmeter/apache-jmeter-5.4/apache-jmeter-5.4/bin"
    return params


def get_central_connections_params(central_connection,test_cases_params):
    try:
        result_dict=central_connection[test_cases_params['ConnectionProfile']]
        return result_dict
    except:
        pass


def get_subscription_params(central_connection,test_cases_params):
    result_dict=central_connection[test_cases_params['SubscriptionFriendlyName']]
    return result_dict
    
def get_master_configuration(master_configuration_list,subscription_name):
    for item in master_configuration_list:
        if item['name'].__contains__(subscription_name):
            return {"name":item['name'],"id":item['id']}
        
def az_login(subscription_params):
    try:
        command="az login --service-principal -u "+subscription_params['AppId']+" -p "+subscription_params['SecretKey']+" --tenant "+subscription_params['TenantId']
        status=Popen(command,shell=True ,stdout=subprocess.PIPE)
        output=status.communicate()[0]
        encoding = 'utf-8'
        decoded_output = output.decode(encoding)
        json_file=json.loads(decoded_output)
        #If the subscriptions is disabled or not
        if json_file[0]['state']=="Enabled":
            return 1
        else:
            return 0
    except:
        return 0
    
def Orchestrator(subscription_name):
    global credentials,instance_sheet_id,errors_sheet_id,run_log_sheet_id,master_configuration,parameter_files_folder_id,jmeter_resources_folder_id
    start_time =  datetime.datetime.now()
    try:
        instance_sheet_range="Test Cases"
        central_credentials_sheet_range="Connections"
        #Reading Test Cases sheet from instance sheet and sheet1 from Central connections sheet
        test_cases_df=read_spreadsheet_to_df(credentials, instance_sheet_id, instance_sheet_range)
        central_credentials=read_credentials_to_dict(credentials,central_credentials_sheet_id,"Sheet1")
        for index in test_cases_df.index:
            test_cases_params=get_test_cases_params(test_cases_df,index)
            #Getting credentials if any based on connectionfriendlyname
            central_connection_params=get_central_connections_params(central_credentials,test_cases_params)
            #Central credentials is required only for SQL and NoSQL Databases. For other resources parameters only from Test Cases Sheets is required.
            if central_connection_params:
                #Merging parameters from central connections sheet and test cases sheet and storing in params dict
                params={**test_cases_params,**central_connection_params}
            else:
                params=test_cases_params
            #Performance testing with multiple subscriptions only for azure cloud
            if params['IsScope']=="Yes":
                #subscription_params=get_subscription_params(central_credentials,test_cases_params)
                #login_status=az_login(subscription_params)
                #if login_status==0:
                    #log_error(params,"Subscription login failed with given credentials or is disabled.")
                    #continue
                #Azure

                if params['ConfigType']=="Azure-Function-Execute":
                    if not azure_function_execute(params):
                        flag=0
                if params['ConfigType']=="Azure-WebApp-Connect":
                    if not azure_webapp_connect(params):
                        flag
                #GCP
                if params['ConfigType']=="GCP-FireStore-Query" and params['IsScope']=="Yes":
                    if not gcp_firestore_query(params):
                        flag=0

                #AWS     
                if params['ConfigType']=="AWS-RDSPostgres-Query" and params['IsScope']=="Yes":
                    if not aws_rds_query(params):
                        flag=0
                #IBM
                if params['ConfigType']=="IBM-DB2-Query" and params['IsScope']=="No":
                    if not ibm_db2_query(params):
                        flag=0

        end_time =  datetime.datetime.now()
        update_run_log(start_time,end_time)
        return flag
    except Exception as e:
        print(e)
        pass


#Python Server
hostName = "0.0.0.0"
serverPort = 8080
class MyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        response="Server waiting for request.!"
        path=self.path.split("/")
        if len(path)>2 and path[-2]=="Orchestrator":
            subscription_name=path[-1].replace("%20"," ")
            response=Orchestrator(subscription_name)
            #Orchestrator=>reponse:1 or reponse:0
        self.send_response(200)
        json_str={"response":response}
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(bytes(json.dumps(json_str, ensure_ascii=False), 'utf-8'))
        
if __name__ == "__main__":        
    webServer = HTTPServer((hostName, serverPort), MyServer)
    print("Server started http://%s:%s" % (hostName, serverPort))
    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        pass

    webServer.server_close()
    print("Server stopped.")
    














