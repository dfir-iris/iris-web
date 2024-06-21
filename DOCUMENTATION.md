# DFIR-IRIS: Documentation API REST

You will find the endpoints API listing for DFIR-IRIS v2.0.4.

## Resource Listing 

CASE:
 ```
 
verbe : POST
url : /manage/cases/add (old url) => POST /cases
description : add a case

verbe : GET
url : /manage/cases/list (old url) => GET /cases
description : get list of cases

verbe : PUT
url : /manage/cases/close/{case_id} (old url) => PUT /cases/close/{case_id}
description : close a case

verbe : PUT
url : /manage/cases/reopen/{case_id} (old url) => PUT /cases/reopen/{case_id}
description : reopen a case 

verbe : DELETE
url : /manage/cases/delete/{case_id} (old url) => DELETE /cases/{case_id}
description : delete a case with his ID

verbe : PUT
url : /manage/cases/update/{case_id} (old url) => PUT /cases/{case_id}
description : update a case with his ID

```

IOC OF A CASE : 

```

verbe : GET
url : /case/ioc/list (old url) => GET /case/ioc
description : get a ioc list of a case 

verbe : GET
url : /case/ioc/{ioc_id} (old url) => GET /case/ioc/{ioc_id}
description : get ioc of a case 

verbe : POST
url : /case/ioc/add  (old url) => POST /case/ioc
description : add ioc of a case

verbe : DELETE
url : /case/ioc/delete/{ioc_id} (old url) => DELETE /case/ioc/{ioc_id}
description : delete ioc of a case

verbe : PUT
url : /case/ioc/update/{ioc_id}  (old url) => PUT /case/ioc
description : update ioc of a case

``` 

TASK OF CASE :

```
verbe : GET
url : /case/tasks/list (old url) => GET /case/tasks
description : get a tasks list 

verbe : POST
url : /case/tasks/add (old url) => POST /case/tasks
description : add tasks of case 

verbe : DELETE
url : /case/tasks/delete/{task_id} (old url) => DELETE /case/tasks/{task_id}
description : delete tasks of case 

verbe : GET
url : /case/tasks/{task_id} (old url) => GET /case/tasks/{task_id}
description : get a specific task of case 

verbe : PUT 
url : /case/tasks/update/{task_id} (old url) => PUT /case/tasks/{task_id} 
description : update a task of a case 


```

ASSET OF CASE :

```
verbe : GET
url : /case/assets/list  (old url) => GET /case/assets
description : get a list of assets of a case

verbe : GET
url : /case/assets/{asset_id} (old url) => GET /case/assets/{asset_id} 
description : get one asset of a case

verbe : POST
url : /case/assets/add  (old url) => POST /case/assets
description : add an asset of a case

verbe : PUT
url : /case/assets/update/{asset_id}  (old url) => PUT /case/assets/{case_id}
description : update an asset of a case 

verbe : DELETE
url : /case/assets/delete/{asset_id} (old url) => DELETE /case/assets/{case_id}
description : delete an asset of a case

```

NOTES OF A CASE :

```
verbe : POST
url :  /case/notes/add (old url) => POST /case/notes
description :  add a note of case 

verbe : GET
url :  /case/notes/{note_id} (old url) => GET /case/notes/{note_id}
description :  get a note of case 

verbe : PUT
url :  /case/notes/update/{note_id} (old url) => PUT /case/notes
description :  update a note of case 

verbe : DELETE
url :  /case/notes/delete/{note_id} (old url) => DELETE /case/notes/{note_id}
description :  delete a note of case 

verbe : PUT
url :  /case/notes/search (old url) => GET /case/notes/search
description :  search a note in case 

verbe : GET
url :  /case/notes/groups/list  (old url) => GET /case/notes/groups
description : get a list of groups of notes  

verbe : GET
url :  /case/notes/groups/{group_id}  (old url) => GET /case/notes/groups/{group_id}
description :  get a group from note of a case

verbe : POST
url :  /case/notes/groups/add  (old url) => POST /case/notes/groups/
description : add a group from note of a case

verbe : PUT
url :  /case/notes/groups/update/{group_id}  (old url) => PUT /case/notes/groups/{group_id}
description : update a group from note of a case

verbe : DELETE
url :  /case/notes/groups/delete/{group_id} (old url) => DELETE /case/notes/groups/{group_id}
description : delete a group from note of a case

verbe : GET
url :  /case/notes/directories/filter  (old url) => GET /case/notes/directories
description :  filter a directory from note of a case

verbe : POST
url :  /case/notes/directories/add (old url) => POST /case/notes/directories/{directories_id}
description : add a directory from note of a case

verbe : PUT
url :  /case/notes/directories/update/{directory_id}  (old url) => PUT /case/notes/directories/{directories_id}
description : update a directory from note of a case

verbe : DELETE
url :  /case/notes/directories/delete/{directory_id}  (old url) => DELETE /case/notes/directories/{directories_id}
description : delete a directory from note of a case


```

TIMELINE OF A CASE :

```
verbe : GET
url :  /case/timeline/events/list/filter/{id} (old url) => GET /case/timeline/events/list/{id}
description : 

verbe : GET
url :  /case/timeline/advanced-filter (old url) => GET /case/timeline/advanced-filter
description : 

verbe : GET
url :  /case/timeline/events/list (old url) => GET /case/timeline/events
description : get list of timelime events 

verbe : GET
url :  /case/timeline/state (old url) => GET /case/timeline/state
description : give the state of timeline 

verbe : POST
url :  /case/timeline/events/add (old url) => POST /case/timeline/events/
description : 

verbe : GET
url :  /case/timeline/events/{event_id}   (old url) => GET /case/timeline/events/
description : 

verbe : PUT
url : /case/timeline/events/update/{event_id}   (old url) => PUT /case/timeline/events/
description : 

verbe : DELETE
url :  /case/timeline/events/delete/{event_id}   (old url) => DELETE /case/timeline/events/
description : 

```

EVIDENCE OF A CASE :

```
verbe : GET
url :  /case/evidences/list (old url) => DELETE /case/evidences/
description : 

verbe : POST
url :  /case/evidences/add (old url) => DELETE /case/evidences/
description : 

verbe : GET
url : /case/evidences/{evidence_id} (old url) => DELETE /case/evidences/{evidence_id}
description : 

verbe : DELETE
url :  /case/evidences/delete/{evidence_id} (old url) => DELETE /case/evidences/
description : 

verbe : PUT
url :  /case/evidences/update/{evidence_id} (old url) => PUT /case/evidences/
description : 


```
le reste :
```
/case/summary/update
/case/tasklog/add
/case/export 
/case/{object_name}/{object_id}/comments/add 
/case/{object_name}/{object_id}/comments/list 
/case/{object_name}/{object_id}/comments/{comment_id}/delete 
/case/{object_name}/{object_id}/comments/{comment_id}/edit 
/manage/cases/filter 
  ```

ALERT:
  ```
verbe : POST 
url : /alerts/add => POST /alerts
description: add alert
   ```

GROUP :
  ```
verbe : POST 
url : /manage/groups/add (old url) => POST /groups
description : add a new group with authorizations 

verbe : PUT 
url : /manage/groups/update/{group_id}  (old url) => PUT /groups
description : update a group 

verbe : POST 
url : /manage/groups/{group_id}/members/update  (old url) => POST /groups/{group_id}
description : update a member of a group

verbe : DELETE 
url : /manage/groups/delete/{group_id}  (old url) => DELETE /groups/{group_id}
description : delete a group 

verbe : DELETE
url : /manage/groups/{group_id}/members/delete/{user_id}  (old url) => DELETE /groups/{group_id}/members/{user_id}
description : delete a member with his ID 

verbe : POST 
url : /manage/groups/{group_id}/cases-access/update  (old url) => PUT /groups/{group_id}/cases-access
description : update case access of a group

verbe : DELETE 
url : /manage/groups/{group_id}/cases-access/delete  => DELETE /groups/{group_id}/cases-access
description : delete case access of a group

verbe : GET
url : /manage/groups/list (old url) => GET /groups
description : get a list of groups 

 ```

 ```

/alerts/{alert_id} 
/alerts/filter 
/alerts/add 
/alerts/update/{alert_id} 
/alerts/batch/update 
/alerts/delete/{alert_id} 
/alerts/batch/delete 
/alerts/escalate/{alert_id} 
/alerts/merge/{alert_id} 
/alerts/unmerge/{alert_id} 
/datastore/list/tree 
/datastore/file/add/{parent_id} 
/datastore/file/info/{file_id} 
/datastore/file/update/{file_id} 
/datastore/file/delete/{file_id} 
/datastore/file/view/{file_id} 
/datastore/file/move/{file_id} 
/datastore/folder/add 
/datastore/folder/delete/{folder_id} 
/datastore/folder/rename/{folder_id} 
/datastore/folder/move/{folder_id} 
/dim/tasks/list/{rows_count} 
/dim/tasks/limited-list 
/dim/hooks/options/{object_type}/list 
/dim/hooks/call 
/global/tasks/list 
/global/tasks/add 
/global/tasks/update/{task_id} 
/global/tasks/delete/{task_id} 
/manage/customers/list 
/manage/customers/{customer_id} 
/manage/customers/add 
/manage/customers/update/{customer_id} 
/manage/customers/delete/{customer_id} 
/manage/customers/{customer_id}/contacts/add
/manage/customers/{customer_id}/contacts/{contact_id}/update 
/manage/users/delete/{user_id} 
/manage/users/update/{user_id} 
/manage/users/add 
/manage/users/{user_id}/groups/update 
/manage/users/{user_id}/cases-access/update 
/manage/users/{user_id}/cases-access/delete 
/manage/users/list
/manage/access-control/recompute-effective-user-ac/{user_id}
/manage/users/{user_id} 
/manage/asset-type/list 
/manage/asset-type/{asset_type_id} 
/manage/asset-type/delete/{asset_type_id} 
/manage/asset-type/add 
/manage/asset-type/update/{asset_type_id} 
/manage/task-status/list 
/manage/task-status/{task_status_id}
/manage/analysis-status/list 
/manage/analysis-status/{analysis_status_id}
/manage/ioc-types/list 
/manage/ioc-types/{ioc_type_id} 
/manage/ioc-types/delete/{ioc_type_id} 
/manage/ioc-types/add 
/manage/ioc-types/update/{ioc_type_id} 
/manage/case-templates/add 
/manage/case-templates/update/{template_id} 
/manage/case-templates/delete/{template_id} 
/manage/case-classifications/list 
/manage/case-classifications/{classification_id} 
/manage/case-classifications/add 
/manage/case-classifications/update/{classification_id} 
/manage/case-classifications/delete/{classification_id} 
/manage/case-states/list 
/manage/case-states/{state_id} 
/manage/case-states/add 
/manage/case-states/update/{state_id} 
/manage/case-states/delete/{state_id} 
/manage/evidence-types/list
/manage/evidence-types/{type_id}
/manage/evidence-types/add
/manage/evidence-types/update/{type_id}
/manage/evidence-types/delete/{state_id}
/api/versions
/api/ping
/manage/groups/delete
/manage/groups/update
/manage/groups/list
/manage/groups/{group_id}
/manage/users/activate
/manage/users/deactivate
/manage/users/renew-api-key
/manage/users/restricted/list                               
/manage/access-control/audit/users
/alerts/batch/merge
/alerts/batch/escalate                           
/case/ioc/upload
/case/ioc/state   
/alerts/<int:alert_id>                      
/case/ioc/{ioc_id}/modal  (return page.html)
/case/ioc/add/modal       (return page.html)
/case/ioc/comments/modal  (return page.html)
/global/tasks/add/modal (return page.html)
/case/ioc/comments/list
/case/ioc/comments/add
/case/ioc/comments/{comments_id}
/case/ioc/comments/{comments_id}/edit
/case/ioc/comments/{comments_id}/delete                              
/case/summary/fetch                               
/manage/analysis-status/search   
/manage/users/renew-akpi-key/{user_id}
/manage/users/groups/update
/manage/users/customer/update
/manage/users/restricted/list              
/case/tasks/add/modal   (return page.html)
/datastore/file/add-interactive
/case/timeline/events/list/{asset_id}

ideal presentation :
verbe : POST 
url : /manage/groups/add (old url)
description : add a new group with authorizations 
parameter : 
type : 
body :
return type :
return : 
  ```

## Difference between 
### Actual state

### Difference between documentation v2.0.4 and code v2.4.7
Difference (1): 
```
/dim/tasks/limited-list

```

### Difference between code v2.4.7 and documentation v2.0.4

Differences (32): 

```
/global/tasks/add/modal (return page.html)
/manage/groups/add
/manage/groups/delete
/manage/groups/update
/manage/groups/list
/manage/groups/{group_id}
/manage/users/activate
/manage/users/deactivate
/manage/users/renew-api-key
/manage/users/restricted/list                               
/manage/access-control/audit/users
/alerts/batch/merge
/alerts/batch/escalate                           
/case/ioc/upload
/case/ioc/state                         
/case/ioc/{ioc_id}/modal  (return page.html)
/case/ioc/add/modal       (return page.html)
/case/ioc/comments/modal  (return page.html)
/case/ioc/comments/list
/case/ioc/comments/add
/case/ioc/comments/{comments_id}
/case/ioc/comments/{comments_id}/edit
/case/ioc/comments/{comments_id}/delete                              
/case/summary/fetch                               
/manage/analysis-status/search   
/manage/users/renew-akpi-key/{user_id}
/manage/users/groups/update
/manage/users/customer/update
/manage/users/restricted/list              
/case/tasks/add/modal   (return page.html)
/datastore/file/add-interactive
/case/timeline/events/list/{asset_id}
```