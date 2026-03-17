from google.cloud import bigquery
from google.cloud.bigquery.table import PrimaryKey, TableConstraints
from google.cloud.exceptions import NotFound

def deploy_full_icm_schema(project_id, dataset_id):
    client = bigquery.Client(project=project_id)

    # Create dataset if it doesn't exist
    dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
    try:
        client.get_dataset(dataset_ref)
        print(f"[-] Dataset {dataset_id} already exists.")
    except NotFound:
        client.create_dataset(bigquery.Dataset(dataset_ref))
        print(f"[+] Created dataset: {dataset_id}")

    # Full dictionary of all 8 tables from your metadata
    tables_to_create = {
        "Worker_Profile": [
            bigquery.SchemaField("Employee_Number", "INT64", mode="REQUIRED", description="Unique Employee Identifier"),
            bigquery.SchemaField("First_Name", "STRING"),
            bigquery.SchemaField("Last_Name", "STRING"),
            bigquery.SchemaField("Supervisor_Emp_Number", "INT64", description="Employee Number of Supervisor"),
        ],
        "Worker_History": [
            bigquery.SchemaField("Employee_Number", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("Location_ID", "INT64"),
            bigquery.SchemaField("Job_Code", "STRING"),
            bigquery.SchemaField("Start_date", "DATE"),
            bigquery.SchemaField("End_date", "DATE"),
        ],
        "Location_Details": [
            bigquery.SchemaField("Location_ID", "INT64", mode="REQUIRED", description="Unique Location Identifier"),
            bigquery.SchemaField("Territory", "STRING"),
            bigquery.SchemaField("Market", "STRING"),
            bigquery.SchemaField("District", "STRING"),
            bigquery.SchemaField("Location_Name", "STRING"),
            bigquery.SchemaField("Store_Name", "STRING"),
        ],
        "Vendor_Program_Details": [
            bigquery.SchemaField("Location_ID", "INT64"),
            bigquery.SchemaField("Vendor_Program_Number", "INT64"),
            bigquery.SchemaField("SKU_ID", "INT64"),
            bigquery.SchemaField("Comp_Plan_ID", "INT64"),
            bigquery.SchemaField("Vendor_ID", "INT64"),
            bigquery.SchemaField("Vendor_Name", "STRING"),
        ],
        "Plan_Details": [
            bigquery.SchemaField("Comp_Plan_Version_ID", "INT64", mode="REQUIRED", description="Primary Key"),
            bigquery.SchemaField("Comp_Plan_ID", "INT64"),
            bigquery.SchemaField("Comp_Plan_Name", "STRING"),
            bigquery.SchemaField("Start_Date", "DATE"),
            bigquery.SchemaField("End_Date", "DATE"),
            bigquery.SchemaField("Plan_applicable_Level", "STRING"),
            bigquery.SchemaField("Time_Period", "STRING"),
            bigquery.SchemaField("Percentage", "INT64"),
        ],
        "Plan_assignment": [
            bigquery.SchemaField("Comp_Plan_ID", "INT64"),
            bigquery.SchemaField("Employee_Number", "INT64"),
            bigquery.SchemaField("Start_Date", "DATE"),
            bigquery.SchemaField("End_Date", "DATE"),
        ],
        "Sale_Details": [
            bigquery.SchemaField("Transaction_ID", "INT64", mode="REQUIRED", description="Primary Key"),
            bigquery.SchemaField("Sale_Transaction_Date", "DATE"),
            bigquery.SchemaField("Location_ID", "INT64"),
            bigquery.SchemaField("Employee_Number", "INT64"),
            bigquery.SchemaField("Total_Sale_Amount", "INT64"),
        ],
        "Fiscal_Calendar_Details": [
            bigquery.SchemaField("Fiscal_Calendar_ID", "INT64", mode="REQUIRED", description="Primary Key"),
            bigquery.SchemaField("Fiscal_Year", "INT64"),
            bigquery.SchemaField("Fiscal_Start_Date", "DATE"),
            bigquery.SchemaField("Fiscal_End_Date", "DATE"),
            bigquery.SchemaField("Quarter_Start_Date", "DATE"),
            bigquery.SchemaField("Quarter_End_Date", "DATE"),
            bigquery.SchemaField("Quarter_Number", "INT64"),
        ]
    }

    for table_id, schema in tables_to_create.items():
        table_ref = dataset_ref.table(table_id)
        try:
            client.get_table(table_ref)
            print(f"[-] Table {table_id} already exists.")
        except NotFound:
            table = bigquery.Table(table_ref, schema=schema)
            
            # Setting Primary Key metadata (Non-enforced, for Optimizer)
            if table_id in ["Worker_Profile", "Location_Details", "Plan_Details", "Sale_Details", "Fiscal_Calendar_Details"]:
                table.table_constraints = TableConstraints(
                    primary_key=PrimaryKey(columns=[schema[0].name]),
                    foreign_keys=[]
                )
            
            client.create_table(table)
            print(f"[+] Created table: {table_id}")

if __name__ == "__main__":
    PROJECT = "glossy-buffer-411806"
    DATASET = "icm_analytics"
    deploy_full_icm_schema(PROJECT, DATASET)
