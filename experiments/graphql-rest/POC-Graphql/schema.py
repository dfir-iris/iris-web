import graphene
from graphene_sqlalchemy import SQLAlchemyObjectType, SQLAlchemyConnectionField
from db import db
from models import Author, Book, Movie


class BookObject(SQLAlchemyObjectType):
    class Meta:
        model = Book
        interfaces = (graphene.relay.Node,)
        description = "Représente les différents livres des auteurs. Contient les champs id, title, description , year, author."

class BookConnection(graphene.relay.Connection):
    class Meta:
        node = BookObject

class MovieObject(SQLAlchemyObjectType):
    class Meta:
        model = Movie
        interfaces = (graphene.relay.Node,)
        description = "Représente les différents films. Contient les champs id, title, description , author."

class MovieConnection(graphene.relay.Connection):
    class Meta:
        node = MovieObject
class AuthorObject(SQLAlchemyObjectType):
    class Meta:
        model = Author
        interfaces = (graphene.relay.Node,)
        description = "Représente les différentes informations de l'utilisateurs."
class AuthorConnection(graphene.relay.Connection):
    class Meta:
        node = AuthorObject

class Query(graphene.ObjectType):
    """Query documentation"""
    node = graphene.relay.Node.Field()

    author = graphene.List(lambda: AuthorObject, username=graphene.String(), description='author documentation')
    book = graphene.List(lambda: BookObject, title=graphene.String())
    movie = graphene.List(lambda: MovieObject, title=graphene.String())

    all_books = SQLAlchemyConnectionField(BookConnection)
    all_authors = SQLAlchemyConnectionField(AuthorConnection)
    all_movies = SQLAlchemyConnectionField(MovieConnection)

    def resolve_author(self, info, **kwargs):
        query = AuthorObject.get_query(info)
        username = kwargs.get('username')
        return query.filter(Author.username == username).all()

    def resolve_book(self, info, **kwargs):
        query = BookObject.get_query(info)
        title = kwargs.get('title')
        return query.filter(Book.title == title).all()

class AddBook(graphene.Mutation):
    class Arguments:
        title = graphene.String(required=True)
        description = graphene.String(required=True)
        year = graphene.Int(required=True)
        username = graphene.String(required=True)
    book = graphene.Field(lambda: BookObject)

    def mutate(self, info, title, description, year, username):
        author = Author.query.filter_by(username=username).first()
        book = Book(title=title, description=description, year=year)
        if author is not None:
            book.author = author
        db.session.add(book)
        db.session.commit()
        return AddBook(book=book)

class Mutation(graphene.ObjectType):
    add_book = AddBook.Field()


schema = graphene.Schema(query=Query, mutation=Mutation, types=[AuthorObject, BookObject])
