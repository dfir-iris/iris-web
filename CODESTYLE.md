# Coding style 

If you wish to develop in DFIR-IRIS, please make sure to read the following tips.

## Workflow

- development is done on branch `develop`
  ```
  git switch develop
  ```
- safe and small modifications may be directly performed on branch `develop`
- modifications which either imply more work or are risky, must be performed on a branch of their own
  ```
  git switch -c <branch-name>
  git push --set-upstream origin <branch-name>
  ```
- when work on the branch is ready to be published, then a pull request (PR) is created from the github interface.
  Do not forget to choose `develop` as the base branch (by default it is set to `master`,
  more information [here](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request#changing-the-branch-range-and-destination-repository)).


### Commits
Try to follow the repository convention:

- If it's not linked to an issue, use the format `[action] Commit message`, with `action` being a 3 letters action related to the commit, eg `ADD`for additions, `DEL` for deletions, `IMP` for improvements, etc.
- If it's linked to an issue, prepend with the issue ID, i.e `[#issue_id][action] Commit message`

## License header

New files should be prefixed by the following license header, where `${current_year}` is replaced by the current year
(for instance 2024):
```
#  IRIS Source Code
#  Copyright (C) ${current_year} - DFIR-IRIS
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
```

## Python coding rules

* do not prefix files with any shebang, such as:
```python
#!/usr/bin/env python3
```
* use string interpolation (f-strings, https://peps.python.org/pep-0498/),
  rather than the string `format` method (https://podalirius.net/en/articles/python-format-string-vulnerabilities/)
* prefix names of all private fields, methods and variables with underscore (_).
  This allows any code maintainer to immediately spot which code elements can be freely modified
  without having to worry about the external context.
  Note: private elements are only called within the modules in which they are defined.

## Javascript coding rules

* use `===` instead of `==`
* use `!==` instead of `!=`
* use [template literal](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Template_literals) instead of [string addition](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Addition)

## Code
The code should be pretty easy to apprehend. It's not perfect, but it will improve over time.
Some documentation about development is available [here](https://docs.dfir-iris.org/development/).   
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
