import logging
import azure.functions as func
import pandas as pd
#To Authenticate and read/write to sheets.
import sheeets_api

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    dashboard_file=open('DashboardMaster.html',mode='r')
    file_content=dashboard_file.read()
    df=pd.read_csv('config.csv')
    locations=df['Location'].unique()
    for location in locations:
        loc=df[df.Location==location]
        total_len=len(loc)
        high_performant=(len(loc[loc.Errors==0])/total_len)*100
        avg_performant=(len(loc[(loc.Errors>0) & (loc.Errors<=25)])/total_len)*100
        bad_performant=(len(loc[loc.Errors>25])/total_len)*100
        high_str="##"+location+"-HIGHLY PERFORMANT##"
        avg_str="##"+location+"-AVERAGE PERFORMANT##"
        bad_str="##"+location+"-BAD PERFORMANT##"
        file_content=file_content.replace(high_str,str(high_performant)).replace(avg_str,str(avg_performant)).replace(bad_str,str(bad_performant))  
    df1=df[['ConfigType','PassOrFail']].values.tolist()
    function_count_pass=0
    webapps_count_pass=0
    largedb_count_pass=1
    nosqldb_count_pass=0
    microdb_count_pass=0
    function_count_fail=0
    webapps_count_fail=0
    largedb_count_fail=0
    nosqldb_count_fail=0
    microdb_count_fail=0

    for i in df1:
        if(i[0].startswith("Azure-Function")):
            if(i[1]=="Pass"):
                function_count_pass+=1
            else:
                function_count_fail+=1
       
        if(i[0].startswith("Azure-WebApp")):
            if(i[1]=="Pass"):
                webapps_count_pass+=1
            else:
                webapps_count_fail+=1
        if(i[0].startswith("Azure-CosmosDB")):
            if(i[1]=="Pass"):
                nosqldb_count_pass+=1
            else:
                nosqldb_count_fail+=1
        if(i[0].startswith("Azure-SQLDB")):
            if(i[1]=="Pass"):
                microdb_count_pass+=1
            else:
                microdb_count_fail+=1

       
    file_content=file_content.replace( "$$functionpasscount",str(function_count_pass)).replace("$$functionfailcount",str(function_count_fail)).replace("$$webappspasscount",str(webapps_count_pass)).replace("$$webappsfailcount",str(webapps_count_fail)).replace("$$largedbpasscount",str(largedb_count_pass)).replace("$$largedbfailcount",str(largedb_count_fail))    

    file_content=file_content.replace( "$$nosqldbpasscount",str(nosqldb_count_pass)).replace( "$$nosqldbfailcount",str(nosqldb_count_fail)).replace( "$$microdbfailcount",str(microdb_count_fail)).replace( "$$microdbpasscount",str(microdb_count_pass))



    dashboard_file.close()
    dashboard_file_update=open('CloudGaugeDashBoard.html',mode='w')
    dashboard_file_update.write(file_content)
    dashboard_file_update.close()
    upload_dasboard_file_to_blob('CloudGaugeDashboard.html')




