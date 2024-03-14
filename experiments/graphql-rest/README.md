# Study between Graphql and REST 

## GraphQL
Graphql is a query langage and and server-side runtime environment for application programming interfaces (APIs).
It allows only the requested resources to be provided to clients. It is possible to deploy it within your own GraphiQL development environment.

### Schema 
A schema defines the typical system of the GraphQL API.
It describes the complete set of data (object, field, relationship, etc.).
Client calls are validated and executed from the schema.


### Schema example
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
### Request example 
To query the database, we send requests.
For the example below we want to recover all the books.
``` bash
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
### Request answer
``` bash
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
### Resolver
Once the query has been verified through its syntax and via the server schema, GraphQL calls on the resolvers.
The resolver will then retrieve the data from the right place depending on what it receives.



``` bash
    def resolve_author(self, info, **kwargs):
        query = AuthorObject.get_query(info)
        username = kwargs.get('username')
        return query.filter(Author.username == username).all()

    def resolve_book(self, info, **kwargs):
        query = BookObject.get_query(info)
        title = kwargs.get('title')
        return query.filter(Book.title == title).all()
```
### Mutation

The mutation type defines the operations that will modify the data on the server. (For example actions: create and delete).
``` bash
mutation {
  addBook(
    username:"elise",
    title:"Intro to GraphQL",
    description:"POC GraphQL",
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
## REST api
Application programming interface that respects the constraints of the REST architecture.
This is a set of conventions and good practices to be implemented. Allows you to interact with RESTful web services.

## Comparison between Graphql and REST
| Project standard       | REST | GraphQL |
|------------------------|:----:|:-------:|
| Avoid overflow of data |      |    X    |
| Flexible request       |      |    X    |
| File upload            |  X   |         |
| Http cache             |  X   |         |
| Documentation          |  X   |    X    |
| Error alert            |  X   |    X    |


### Data collection requirement:
- By using GraphQL we avoid over-recovery or under-recovery of data, which will avoid overloading the bandwidth.
- REST is not flexible on response structure.

### GraphQL IDE:

There are two main platforms for developing in GraphQL (GraphOs and GraphiQL).
These are graphical interfaces for writing queries and mutations.

- GraphOs: developed by Apollo, allows you to check the structure of a schema via "schema checks" and offers auto-completion of fields (under MIT license).

https://www.apollographql.com/docs/graphos/

- GraphiQL: Does introspection to retrieve our API documentation, also offers auto-completion of fields (under MIT licensing).

https://github.com/graphql/graphiql/blob/main/packages/graphiql/README.md

- GraphQL-playground: Interactive GraphQL IDE developed by Prisma and based on GraphiQL, (under MIT license).

https://github.com/graphql/graphql-playground

### Learning curve:
- REST has a large source of documentation, many tools and resources available.
- GraphQL has fewer resources but we still find the Apollo forum dedicated to the discussion on GraphQL, as well as Apollo GraphOS.

Apollo community link:

https://community.apollographql.com/
https://www.apollographql.com/docs/graphos/

### File upload :
- File uploading is not taken into account by GraphQL, you will have to find another solution (the graphql-upload library).

https://github.com/lmcgartland/graphene-file-upload

### Documentation :
- For GraphQL, you can use different tools such as dociql or spectaql (self-supported documentation) which generates documentation in a separate "public" directory.

Dociql allows you to generate:
- examples of request/response with the "Try it now" option.
- examples of diagrams.

### Error alert :
- GraphQL introduced error tables as options to deal with the irrelevance of HTTP error codes. Example: Multiple operations send in the same query, but it is impossible for a query to partially fail, thus returning wrong and real data.

### HTTP cache :
- GraphQL does not take into account HTTP caching processes. (Using client-side cache via ApolloClient for example).
- GraphQl lacks native caching support, one must implement custom caching strategies.
- Be careful, when GraphQL queries become excessively complex and nested, this can cause significant overhead on the server.
- REST uses standard HTTP caching practices.

Error example  :
``` bash  
{
  "errors": [
    {
      "message": "Cannot query field \"author\" on type \"MovieObject\". Did you mean \"authorId\"?",
      "locations": [
        {
          "line": 7,
          "column": 10
        }
      ]
    }
  ]
}
```

### Security :
- To implement authorization mechanisms, you can use OSO.

https://www.osohq.com/post/graphql-authorization

Different GraphQL libraries (python) between Graphene, Strawberry and Ariadne:

| Critère                     |      Ariadne       | Graphene | Strawberry |
|-----------------------------|:------------------:|:--------:|:----------:|
| Schema-first implementation |        YES         |    NO    |     NO     |
| Code-first implementation   |         NO         |   YES    |    YES     |
| Users                       |         2k         |    8k    |     4k     |
| License                     | BSD 3-Clause "New" |   MIT    |    MIT     |
| Current version             |        0.22        |  3.3.0   |  0.220.0   |

Comparison link:

https://www.libhunt.com/compare-graphene-vs-strawberry
https://graphql.org/code/#python

Using sqlalchemy with strawberry:

https://github.com/strawberry-graphql/strawberry-sqlalchemy

Example Flask application with GraphQL:

https://github.com/graphql-python/graphql-server/blob/master/docs/flask.md

Using Postgraphile to automatically generate schemas from the PostgresSQL database:

https://www.graphile.org/postgraphile/

Link about mutation update :

https://www.twilio.com/en-us/blog/graphql-apis-django-graphene



