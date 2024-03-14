import graphene
from graphene_sqlalchemy import SQLAlchemyObjectType, SQLAlchemyConnectionField
from db import db
from models import Author, Book, Movie


class BookObject(SQLAlchemyObjectType):
    """Book object documentation"""
    class Meta:
        model = Book
        interfaces = (graphene.relay.Node,)
        description = "Documentation about different authors."

class BookConnection(graphene.relay.Connection):
    class Meta:
        node = BookObject

class MovieObject(SQLAlchemyObjectType):
    """Movie object documentation"""
    class Meta:
        model = Movie
        interfaces = (graphene.relay.Node,)
        description = "Documentation about different movies."

class MovieConnection(graphene.relay.Connection):
    class Meta:
        node = MovieObject
class AuthorObject(SQLAlchemyObjectType):
    """Author object documentation"""
    class Meta:
        model = Author
        interfaces = (graphene.relay.Node,)
        description = "Documentation about user informations."
class AuthorConnection(graphene.relay.Connection):
    class Meta:
        node = AuthorObject

class Query(graphene.ObjectType):
    """Query documentation"""
    node = graphene.relay.Node.Field()

    author = graphene.List(lambda: AuthorObject, username=graphene.String(), description='author documentation')
    book = graphene.List(lambda: BookObject, title=graphene.String(), description='book documentation')
    movie = graphene.List(lambda: MovieObject, title=graphene.String(), description='movie documentation')

    book_all = graphene.List(lambda: BookObject, description='book all documentation')
    movie_all = graphene.List(lambda: MovieObject, description='movie all documentation')
    author_all = graphene.List(lambda: AuthorObject, description='author all documentation')

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

    def resolve_book_all(self, info):
        query = BookObject.get_query(info)
        return query.all()

    def resolve_movie_all(self, info):
        query = MovieObject.get_query(info)
        return query.all()

    def resolve_author_all(self, info):
        query = AuthorObject.get_query(info)
        return query.all()


class AddBook(graphene.Mutation):
    """Mutation Addbook """

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


class UpdateBook(graphene.Mutation):
    """Mutation Updatebook """
    class Arguments:
        title = graphene.String(required=True)
        description = graphene.String(required=True)
        year = graphene.Int(required=True)
        author_id= graphene.Int(required=False)
    book = graphene.Field(lambda: BookObject)

    def mutate(self, info, title, description, year, author_id):

        book_instance = Book.query.filter_by(title=title).first()

        if book_instance:
            book_instance.description = description
            book_instance.year = year
            book_instance.author_id = author_id
            db.session.commit()
            return UpdateBook(book=book_instance)
        return UpdateBook(book=None)


class Mutation(graphene.ObjectType):
    """Mutation documentation"""
    add_book = AddBook.Field()
    update_book = UpdateBook.Field()


schema = graphene.Schema( query=Query, mutation=Mutation, types=[AuthorObject, BookObject, MovieObject])
print(schema)
