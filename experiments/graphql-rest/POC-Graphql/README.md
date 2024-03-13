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
schema {
  query: Query
  mutation: Mutation
}

type AddBook {
  book: BookObject
}

type AuthorConnection {
  pageInfo: PageInfo!
  edges: [AuthorEdge]!
}

type AuthorEdge {
  node: AuthorObject
  cursor: String!
}

type AuthorObject implements Node {
  id: ID!
  username: String!
  email: String!
  books(before: String, after: String, first: Int, last: Int): BookObjectConnection
}

enum AuthorObjectSortEnum {
  ID_ASC
  ID_DESC
  USERNAME_ASC
  USERNAME_DESC
  EMAIL_ASC
  EMAIL_DESC
}

type BookConnection {
  pageInfo: PageInfo!
  edges: [BookEdge]!
}

type BookEdge {
  node: BookObject
  cursor: String!
}

type BookObject implements Node {
  id: ID!
  title: String!
  description: String!
  year: Int!
  authorId: Int
  author: AuthorObject
}

type BookObjectConnection {
  pageInfo: PageInfo!
  edges: [BookObjectEdge]!
}

type BookObjectEdge {
  node: BookObject
  cursor: String!
}

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

type MovieConnection {
  pageInfo: PageInfo!
  edges: [MovieEdge]!
}

type MovieEdge {
  node: MovieObject
  cursor: String!
}

type MovieObject implements Node {
  id: ID!
  title: String!
  description: String!
  authorId: Int
}

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

type Mutation {
  addBook(description: String!, title: String!, username: String!, year: Int!): AddBook
}

interface Node {
  id: ID!
}

type PageInfo {
  hasNextPage: Boolean!
  hasPreviousPage: Boolean!
  startCursor: String
  endCursor: String
}

type Query {
  node(id: ID!): Node
  author(username: String): [AuthorObject]
  book(title: String): [BookObject]
  movie(title: String): [MovieObject]
  allBooks(sort: [BookObjectSortEnum] = [ID_ASC], before: String, after: String, first: Int, last: Int): BookConnection
  allAuthors(sort: [AuthorObjectSortEnum] = [ID_ASC], before: String, after: String, first: Int, last: Int): AuthorConnection
  allMovies(sort: [MovieObjectSortEnum] = [ID_ASC], before: String, after: String, first: Int, last: Int): MovieConnection
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

