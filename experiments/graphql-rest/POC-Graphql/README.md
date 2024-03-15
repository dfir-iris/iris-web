### POC server graphql

``` bash
#  Create a repository 
mkdir graphql-python-api
cd graphql-python-api

# Create a new virtual environment
python3 -m venv myapp

#Activate the virtual environment
source myapp/bin/activate

#Install dependencies
pip install flask ariadne flask-sqlalchemy flask-cors

```
Database Postgres

``` bash
#  Create a database (psql)
psql postgres
CREATE DATABASE db

# Go to the database
\c db

#Create table
CREATE TABLE users (
    ID SERIAL PRIMARY KEY,
    name VARCHAR(30),
    email VARCHAR(30)
    );

#See a table
 SELECT * FROM users;

```

``` bash
#  Open a terminal
python3
```
``` bash
#  Add a user
>>> from app import db, User, Book, Movie
>>> elise = User(username='elise', email='elise@gmail.com')
>>> db.session.add(elise)
>>> db.session.commit()

#Add a book
>>> flaskbook = Book()
>>> flaskbook.title = "Pride and prejudice"
>>> flaskbook.description = "Romance"
>>> flaskbook.year = 2019
>>> flaskbook.author_id = jane.id
>>> db.session.add(flaskbook)
>>> db.session.commit()

#Add a movie
>>> flaskbook = Movie()
>>> flaskmovie.title = "Oppenheimer"
>>> flaskmovie.description = "Science"
>>> flaskmovie.author_id = christopher.id
>>> db.session.add(flaskmovie)
>>> db.session.commit()
```
The database gdb should be available on the interface, port 5433 protocol HTTP -http://localhost:5433

### Graphql schema
``` bash
"""Documentation about user informations."""
type AuthorObject implements Node {
  """The ID of the object"""
  id: ID!
  username: String!
  email: String!
  books(before: String, after: String, first: Int, last: Int): BookObjectConnection
}

"""An object with an ID"""
interface Node {
  """The ID of the object"""
  id: ID!
}

type BookObjectConnection {
  """Pagination data for this connection."""
  pageInfo: PageInfo!

  """Contains the nodes in this connection."""
  edges: [BookObjectEdge]!
}

"""
The Relay compliant `PageInfo` type, containing data necessary to paginate this connection.
"""
type PageInfo {
  """When paginating forwards, are there more items?"""
  hasNextPage: Boolean!

  """When paginating backwards, are there more items?"""
  hasPreviousPage: Boolean!

  """When paginating backwards, the cursor to continue."""
  startCursor: String

  """When paginating forwards, the cursor to continue."""
  endCursor: String
}

"""A Relay edge containing a `BookObject` and its cursor."""
type BookObjectEdge {
  """The item at the end of the edge"""
  node: BookObject

  """A cursor for use in pagination"""
  cursor: String!
}

"""Documentation about different authors."""
type BookObject implements Node {
  """The ID of the object"""
  id: ID!
  title: String!
  description: String!
  year: Int!
  authorId: Int
  author: AuthorObject
}

"""Documentation about different movies."""
type MovieObject implements Node {
  """The ID of the object"""
  id: ID!
  title: String!
  description: String!
  authorId: Int
}

"""Query documentation"""
type Query {
  node(
    """The ID of the object"""
    id: ID!
  ): Node

  """author documentation"""
  author(username: String): [AuthorObject]

  """book documentation"""
  book(title: String): [BookObject]

  """movie documentation"""
  movie(title: String): [MovieObject]

  """book all documentation"""
  bookAll: [BookObject]

  """movie all documentation"""
  movieAll: [MovieObject]

  """author all documentation"""
  authorAll: [AuthorObject]
  allBooks(sort: [BookObjectSortEnum] = [ID_ASC], filter: BookObjectFilter, before: String, after: String, first: Int, last: Int): BookConnection
  allAuthors(sort: [AuthorObjectSortEnum] = [ID_ASC], filter: AuthorObjectFilter, before: String, after: String, first: Int, last: Int): AuthorConnection
  allMovies(sort: [MovieObjectSortEnum] = [ID_ASC], filter: MovieObjectFilter, before: String, after: String, first: Int, last: Int): MovieConnection
}

type BookConnection {
  """Pagination data for this connection."""
  pageInfo: PageInfo!

  """Contains the nodes in this connection."""
  edges: [BookEdge]!
}

"""A Relay edge containing a `Book` and its cursor."""
type BookEdge {
  """The item at the end of the edge"""
  node: BookObject

  """A cursor for use in pagination"""
  cursor: String!
}

"""An enumeration."""
enum BookObjectSortEnum {
  ID_ASC
  ID_DESC
  TITLE_ASC
  TITLE_DESC
  DESCRIPTION_ASC
  DESCRIPTION_DESC
  YEAR_ASC
  YEAR_DESC
  AUTHOR_ID_ASC
  AUTHOR_ID_DESC
}

input BookObjectFilter {
  id: IdFilter
  title: StringFilter
  description: StringFilter
  year: IntFilter
  authorId: IntFilter
  author: AuthorObjectFilter
  and: [BookObjectFilter]
  or: [BookObjectFilter]
}

input IdFilter {
  eq: ID
  in: [ID]
  nEq: ID
  notIn: [ID]
}

input StringFilter {
  eq: String
  ilike: String
  in: [String]
  like: String
  nEq: String
  notIn: [String]
  notlike: String
}

input IntFilter {
  eq: Int
  gt: Int
  gte: Int
  in: [Int]
  lt: Int
  lte: Int
  nEq: Int
  notIn: [Int]
}

input AuthorObjectFilter {
  id: IdFilter
  username: StringFilter
  email: StringFilter
  books: BookObjectRelationshipFilter
  and: [AuthorObjectFilter]
  or: [AuthorObjectFilter]
}

input BookObjectRelationshipFilter {
  containsExactly: [BookObjectFilter]
  contains: [BookObjectFilter]
}

type AuthorConnection {
  """Pagination data for this connection."""
  pageInfo: PageInfo!

  """Contains the nodes in this connection."""
  edges: [AuthorEdge]!
}

"""A Relay edge containing a `Author` and its cursor."""
type AuthorEdge {
  """The item at the end of the edge"""
  node: AuthorObject

  """A cursor for use in pagination"""
  cursor: String!
}

"""An enumeration."""
enum AuthorObjectSortEnum {
  ID_ASC
  ID_DESC
  USERNAME_ASC
  USERNAME_DESC
  EMAIL_ASC
  EMAIL_DESC
}

type MovieConnection {
  """Pagination data for this connection."""
  pageInfo: PageInfo!

  """Contains the nodes in this connection."""
  edges: [MovieEdge]!
}

"""A Relay edge containing a `Movie` and its cursor."""
type MovieEdge {
  """The item at the end of the edge"""
  node: MovieObject

  """A cursor for use in pagination"""
  cursor: String!
}

"""An enumeration."""
enum MovieObjectSortEnum {
  ID_ASC
  ID_DESC
  TITLE_ASC
  TITLE_DESC
  DESCRIPTION_ASC
  DESCRIPTION_DESC
  AUTHOR_ID_ASC
  AUTHOR_ID_DESC
}

input MovieObjectFilter {
  id: IdFilter
  title: StringFilter
  description: StringFilter
  authorId: IntFilter
  and: [MovieObjectFilter]
  or: [MovieObjectFilter]
}

"""Mutation documentation"""
type Mutation {
  """Mutation Addbook """
  addBook(description: String!, title: String!, username: String!, year: Int!): AddBook

  """Mutation Updatebook """
  updateBook(authorId: Int, description: String!, title: String!, year: Int!): UpdateBook
}

"""Mutation Addbook """
type AddBook {
  book: BookObject
}

"""Mutation Updatebook """
type UpdateBook {
  book: BookObject
}

``` 

### Run app.py
``` bash
#  To run the server 
flask run
```
Example request via GraphiQL
``` bash
#  Make a GraphQl query request
{
  allBooks{
    edges{
      node{
        title
        description
        author{
          username
        }
      }
    }
  }
}
```
Answer request via GraphiQL
``` bash
#  Make a GraphQl answer
{
  "data": {
    "allBooks": {
      "edges": [
        {
          "node": {
            "title": "Flask test",
            "description": "The best of Flask",
            "author": {
              "username": "mikedean"
            }
          }
        }
      ]
    }
  }
}
```
Other example request via GraphiQL
``` bash
#  Make a GraphQl query request
{
  allMovies{
    edges{
      node{
        title
        description
        authorId
      }
    }
  }
}
```

``` bash
# Another way to write the query allmovie
{
  movieAll {
     description
    title
  }
}
``` 
Example mutation via GraphiQL
``` bash
#  Make a GraphQl mutation
mutation {
  addBook(
    username:"mikedean",
    title:"Intro to GraphQL",
    description:"Welcome to the course",
    year:2018){
    book{
      title
      description
      author{
        username
      }
    }
  }
}
```
Answer via GraphiQL
``` bash
#  Answer mutation
{
  "data": {
    "addBook": {
      "book": {
        "title": "Intro to GraphQL",
        "description": "Welcome to the course",
        "author": {
          "username": "mikedean"
        }
      }
    }
  }
}
```
Example mutation via GraphiQL (field optional)
``` bash
mutation {
  updateBook(
    title: "Flask test"
    year : 1717
  ) {
    book {
      title
      year
      description
      authorId
    }
  }
}
``` 
Answer via GraphiQL
``` bash
{
  "data": {
    "updateBook": {
      "book": {
        "title": "Flask test",
        "year": 1717,
        "description": "test",
        "authorId": 6
      }
    }
  }
}

``` 
Documentation GraphQL
``` bash
#Install dociql
npm install -g dociql

#Define config.yml
introspection: http://127.0.0.1:5000/graphql-api

servers:
  - url: http://127.0.0.1:5000/
    description: Dev

info:
    title: Your API Title
    description: Markdown enabled description of your api.

domains: []

#  Go to repository dociql and run
dociql -d config.yml
```

Example requests via curl 
``` bash
#  Make a GraphQl query request
curl 'http://127.0.0.1:5000/graphql-api' --request POST --header 'content-type:application/json' -d '{"query": "query{ allMovies { edges { node { title description}}}}"}'

#  Answer 
{"data":{"allMovies":{"edges":[{"node":{"title":"Blues brother","description":"Music"}},{"node":{"title":"Titanic","description":"Romance"}},{"node":{"title":"Oppenheimer","description":"Science"}},{"node":{"title":"Yannick","description":"Humour"}}]}}}

  #  Make a GraphQl mutation request
curl 'http://127.0.0.1:5000/graphql-api' --request POST --header 'content-type:application/json' -d '{"query": "mutation{ addBook(username: \"mikedean\", title: \"Graphql\", description : \"V1\", year: 2018) { book { title }}}"}'

#  Answer
{"data":{"addBook":{"book":{"title":"Graphql"}}}}
```

Pagination
``` bash
#  Select the first 2 movies
{
  allMovies(first:2){
    edges{
      node{
        title
        description
        authorId
      }
    }
  }
}

#  Answer
{
  "data": {
    "allMovies": {
      "edges": [
        {
          "node": {
            "title": "Blues brother",
            "description": "Music",
            "authorId": null
          }
        },
        {
          "node": {
            "title": "Titanic",
            "description": "Romance",
            "authorId": 9
          }
        }
      ]
    }
  }
}

#  Cursor
query ( $cursor: String) {
  allMovies(first :1, before: $cursor){
    edges{
      node{
        title
        description
        authorId
      }
    }
  }
}

#  Answer
{
  "data": {
    "allMovies": {
      "edges": [
        {
          "node": {
            "title": "Blues brother",
            "description": "Music",
            "authorId": null
          }
        }
      ]
    }
  }
}

#Get email of manon 
{
  author (username : "manon"){
    email
  }
}
#Answer
{
  "data": {
    "author": [
      {
        "email": "manon@gmail.com"
      }
    ]
  }
}
```

