# Copyright 2020-2022 Google, LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json, datetime, time, configparser
import decimal

from google.cloud import bigquery
from google.cloud.exceptions import NotFound

import TagEngineUtils as te

config = configparser.ConfigParser()
config.read("tagengine.ini")
BIGQUERY_REGION = config['DEFAULT']['BIGQUERY_REGION']

class BigQueryUtils:
    
    def __init__(self, region=None):
        
        if region:
            self.client = bigquery.Client(location=region)
        else:
            self.client = bigquery.Client(location=BIGQUERY_REGION)

    # API method used by tag export function
    def create_report_tables(self, project, dataset):
        
        success = self.create_dataset(project, dataset)
        
        if success == False:
            return success
        
        created_dataset_table = self.report_table_create(project, dataset, 'catalog_report_dataset_tags', 'dataset')
        created_table_table = self.report_table_create(project, dataset, 'catalog_report_table_tags', 'table')
        created_column_table = self.report_table_create(project, dataset, 'catalog_report_column_tags', 'column')
        
        if created_dataset_table or created_table_table or created_column_table:
            return True
        else:
            return False
    
    # API method used by tag export function
    def truncate_report_tables(self, project, dataset):
        
        truncate_dataset_table = self.report_table_truncate(project, dataset, 'catalog_report_dataset_tags')
        truncate_table_table = self.report_table_truncate(project, dataset, 'catalog_report_table_tags')
        truncate_column_table = self.report_table_truncate(project, dataset, 'catalog_report_column_tags')
        
        if truncate_dataset_table and truncate_table_table and truncate_column_table:
            return True
        else:
            return False
    
    # API method used by tag export function
    def insert_record(self, target_table_id, project, dataset, table, column, tag_template, tag_field, tag_value):    
    
        success = True
        
        current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if column:
            rows_to_insert = [
                {"project": project, "dataset": dataset, "table": table, "column": column, "tag_template": tag_template, "tag_field": tag_field, "tag_value": tag_value, "export_time": current_datetime},
            ]

        elif table:
            rows_to_insert = [
                {"project": project, "dataset": dataset, "table": table, "tag_template": tag_template, "tag_field": tag_field, "tag_value": tag_value, "export_time": current_datetime},
            ]
        
        else:
            rows_to_insert = [
                {"project": project, "dataset": dataset, "tag_template": tag_template, "tag_field": tag_field, "tag_value": tag_value, "export_time": current_datetime},
            ]

        try:
            errors = self.client.insert_rows_json(target_table_id, rows_to_insert)  
        except Exception as e:
            if 'NotFound: 404' in str(e):
                # table was recently truncated and isn't quite ready to be written to
                time.sleep(3)
                try:
                    errors = self.client.insert_rows_json(target_table_id, rows_to_insert)
                except Exception as e:
                     print("Error occurred during report_table_insert: {}".format(e))
                     success = False
        
        return success
        
    # API method used by tag history function
    def copy_tag(self, table_name, table_fields, tagged_table, tagged_column, tagged_values):
        
        #print("*** inside BigQueryUtils.copy_tag() ***")
        exists, table_id, settings = self.history_table_exists(table_name)
        
        if exists != True:
            dataset_id = self.create_dataset(settings['bigquery_project'], settings['bigquery_dataset'])
            table_id = self.create_history_table(dataset_id, table_name, table_fields)

        if tagged_column and tagged_column not in "":
            asset_name = ("{}/column/{}".format(tagged_table, tagged_column))
        else:
            asset_name = tagged_table
            
        asset_name = asset_name.replace("datasets", "dataset").replace("tables", "table")
        #print('asset_name: ', asset_name)
                
        self.insert_history_row(table_id, asset_name, tagged_values)  


############### Internal processing methods ###############

    def create_dataset(self, project, dataset):

        success = True
        dataset_id = bigquery.Dataset(project + '.' + dataset)
        dataset_id.location = BIGQUERY_REGION
        
        try:
            dataset_status = self.client.create_dataset(dataset_id, exists_ok=True)  
            #print("Created dataset {}".format(dataset_status.dataset_id))
            return success
        except Exception as e:
            print('Error occurred in create_dataset ', dataset_id, '. Error message: ', e)
            success = False
        return success
    
    # used by tag export function
    def report_table_create(self, project, dataset, table, table_type):
        
        created = True
        
        table_id = project + '.' + dataset + '.' + table
        table_ref = bigquery.Table.from_string(table_id)

        try:
            table = self.client.get_table(table_ref)
            created = False
            return created
              
        except NotFound:

            if table_type == 'dataset':
                schema = [
                    bigquery.SchemaField("project", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("dataset", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("tag_template", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("tag_field", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("tag_value", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("export_time", "DATETIME", mode="REQUIRED"),
                ]
            elif table_type == 'table':
               schema = [
                   bigquery.SchemaField("project", "STRING", mode="REQUIRED"),
                   bigquery.SchemaField("dataset", "STRING", mode="REQUIRED"),
                   bigquery.SchemaField("table", "STRING", mode="REQUIRED"),
                   bigquery.SchemaField("tag_template", "STRING", mode="REQUIRED"),
                   bigquery.SchemaField("tag_field", "STRING", mode="REQUIRED"),
                   bigquery.SchemaField("tag_value", "STRING", mode="REQUIRED"),
                   bigquery.SchemaField("export_time", "DATETIME", mode="REQUIRED"),
               ] 
            else:
                schema = [
                    bigquery.SchemaField("project", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("dataset", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("table", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("column", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("tag_template", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("tag_field", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("tag_value", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("export_time", "DATETIME", mode="REQUIRED"),
                ]

            table = bigquery.Table(table_id, schema=schema)
            table.time_partitioning = bigquery.TimePartitioning(type_=bigquery.TimePartitioningType.DAY, field="export_time") 
            table = self.client.create_table(table)
            print("Created table {}".format(table.table_id))  
            return created
        
        return created
    
    # used by tag export function    
    def report_table_truncate(self, project, dataset, table):
        
        try:
            self.client.query('truncate table ' + project + '.' + dataset + '.' + table).result()
        except Exception as e:
            print('Error occurred during report_table_truncate ', e)
                  
    # used by tag history function
    def history_table_exists(self, table_name):
        
        store = te.TagEngineUtils()
        enabled, settings = store.read_tag_history_settings()
        
        if enabled == False:
            return enabled, settings
        
        bigquery_project = settings['bigquery_project']
        bigquery_region = settings['bigquery_region']
        bigquery_dataset = settings['bigquery_dataset']
        
        dataset_id = self.client.dataset(bigquery_dataset, project=bigquery_project)
        table_id = dataset_id.table(table_name)
        
        try:
            self.client.get_table(table_id) 
            exists = True 
            #print("Tag history table {} already exists.".format(table_name))
        except NotFound:
            exists = False
            print("Tag history table {} not found.".format(table_name))
        
        return exists, table_id, settings
    
    # used by tag history function
    def create_history_table(self, dataset_id, table_name, fields):
        
        schema = [bigquery.SchemaField('event_time', 'DATETIME', mode='REQUIRED'), \
                  bigquery.SchemaField('asset_name', 'STRING', mode='REQUIRED')]

        for field in fields:
            
            col_name = field['field_id']
            
            if field['field_type'] == 'string':
                col_type = 'STRING'
            
            if field['field_type'] == 'enum':
                col_type = 'STRING'
                
            if field['field_type'] == 'double':
                col_type = 'NUMERIC'
                
            if field['field_type'] == 'bool':
                col_type = 'BOOLEAN'
                
            if field['field_type'] == 'timestamp':
                col_type = 'TIMESTAMP'
                
            if field['field_type'] == 'datetime':
                col_type = 'TIMESTAMP' # datetime fields should be mapped to timestamps in BQ because they actually contain a timezone

            if field['field_type'] == 'richtext':
                col_type = 'STRING' 

            if field['is_required'] == True:
                mode = "REQUIRED"
            else:
                mode = "NULLABLE"
                
            schema.append(bigquery.SchemaField(col_name, col_type, mode=mode))
        
        table_id = dataset_id.table(table_name)
        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(type_=bigquery.TimePartitioningType.DAY, field="event_time")  
        table = self.client.create_table(table, exists_ok=True)  
        
        print("Created table {}.{}.{}".format(table.project, table.dataset_id, table.table_id))        
        table_id = ("{}.{}.{}".format(table.project, table.dataset_id, table.table_id))
        
        return table_id
    
    # writes tag history record
    def insert_history_row(self, table_id, asset_name, tagged_values):
        
        row = {'event_time': datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f'), 'asset_name': asset_name}
        
        for tagged_value in tagged_values:
            
            #print('tagged_value: ' + str(tagged_value))
            
            if 'field_value' not in tagged_value:
                continue
            
            if isinstance(tagged_value['field_value'], decimal.Decimal):
                row[tagged_value['field_id']] = float(tagged_value['field_value'])
            elif isinstance(tagged_value['field_value'], datetime.datetime) or isinstance(tagged_value['field_value'], datetime.date):
                row[tagged_value['field_id']] = tagged_value['field_value'].isoformat()
            else:
                row[tagged_value['field_id']]= json.dumps(tagged_value['field_value'], default=str)
                row[tagged_value['field_id']]= tagged_value['field_value']
    
        #print('insert row: ' + str(row))
        row_to_insert = [row,]

        try:
            self.client.insert_rows_json(table_id, row_to_insert)  
        
        except Exception as e:
            if 'NotFound: 404' in str(e):
                # table isn't quite ready to be written to
                time.sleep(3)
                errors = self.client.insert_rows_json(table_id, row_to_insert)  
            else:    
                print("Error while inserting row into BQ history table: {}", e)
    
if __name__ == '__main__':
    
    bqu = BigQueryUtils()
    bqu.truncate_report_tables('tag-engine-develop', 'reporting')
    
        
        
        