# Coding style 

If you wish to develop in DFIR-IRIS, please make sure to read the following tips.   

## Commits 
Try to follow the repository convention : 

- If it's not linked to an issue, use the format `[action] Commit message`, with `action` being a 3 letters action related to the commit, eg `ADD`for additions, `DEL` for deletions, `IMP` for improvements, etc.
- If it's linked to an issue, prepend with the issue ID, i.e `[#issue_id][action] Commit message` 

## Code
The code should be pretty easy to apprehend. It's not perfect but it will improve over time.   
Some documentation about development is available [here](https://dfir-iris.github.io/development/).   
Here are the main takes : 

- **Routes** : these are the things that describes how URI should be handled. Routes are split by categories as in the UI menu. 
They are defined in `source > app > blueprints`. A route providing a web page (i.e non API) relies on templates. 
Each page template is present in the `templates` directory of the target route. 
- **Database requests**: we are trying to split the DB code from the routes code. This is partially done and will improve over time. The DB code is provided in `source > app > datamgmt`.
- **HTML pages**: as specified above each page template is set in the `templates` directory of the corresponding route. These templates are based on layouts, which are defined in `source > app > templates`. 
- **Static contents** : images, JS and CSS are defined in `source > app > static > assets`.

If your code implies database changes, please create an alembic migration script.  
```
alembic -c app/alembic.ini revision -m <What's changed>
```
And then modifies the script in `source > app > alembic` so that the migration can be done automatically.  