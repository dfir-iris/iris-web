# Etude entre Graphql et REST

## GraphQL
Graphql est un langage de requête et un environnment d'exécution côté serveur pour les interfaces de programmation d'application (API).
Il permet de fournir uniquement les ressources demandées aux clients. Il est possible de le déployer au sein de son propre environnement de développement GraphiQL.

### Schéma 
Un schéma définit le système type de l'API GraphQL.
Il décrit l'ensemble complet de données (objet, champ, relation, ...).
Les appels du clients sont validés et exécutés à partir du schéma. 


### Exemple de schéma
``` bash
type Book{

    id :  PRIMARY KEY
    title : VARCHAR(30)
    description : VARCHAR (30)
    year : VARCHAR(30)
    author_id : VARCHAR(30)
    
}

type Author{

    id : VARCHAR(30),
    username : VARCHAR(30),
    email : VARCHAR(30)
    
}
``` 
### Exemple de requête
Pour interroger la base de donnée, on envoie des requêtes.
Pour l'exemple ci-dessous on souhaite récupérer tous les livres.
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
### Réponse de la requête
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
### Resolveur
Une fois la requête vérifiée de part sa syntaxe et via le schéma du serveur, GraphQL fait appel aux resolveurs.
Le resolveur va alors récupérer la donnée au bon endroit en fonction de ce qu'il reçoit. 

``` bash
class Query(graphene.ObjectType):
    node = graphene.relay.Node.Field()
    all_books = SQLAlchemyConnectionField(BookObject)
    all_users = SQLAlchemyConnectionField(UserObject)
    all_movies = SQLAlchemyConnectionField(MovieObject)
```
### Mutation
Chaque schéma à un type racine pour les requêtes et les mutations.
Le type mutation définit les opérations qui vont modifier les données sur le serveur. (Par exemple les actions : créer et supprimer)
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
## Api REST
Interface de programmation d'application qui respecte les contraintes de l'architecture REST. 
Il s'agit d'un ensemble de conventions et de bonnes pratiques à mettre en oeuvre. Permet d'interagir avec les services web RESTful.

## Comparaison entre GraphQL et REST
| Contexte du projet                        | REST | GraphQL |
|-------------------------------------------|:----:|:-------:|
| Une source de donnée (PostgreSQL)         |  X   |         |
| Evite la sur-récupération de donnée       |      |    X    |
| Requêtes flexibles                        |      |    X    |
| Téléchargement de fichier                 |  X   |         |
| Performance (cache)                       |  X   |         |
| Documentation                             |  X   |    X    |
| Plusieurs ressources accesibles à la fois |      |    X    |
| Message d'erreur                          |  X   |    X    |


Besoin en matière de collecte de données 
- En utilisant GraphQL on évite la sur-récupération ou sous-récupération de données, ce qui permettra de ne pas surcharger la bande passante.
- REST n'est pas flexible sur la structure de réponse.

IDE GraphQL 

On retrouve deux grandes plateformes pour développer en GraphQL.
Il s'agit d'interfaces graphiques pour écrire des requêtes et des mutations.

- GraphOs : développé par Apollo, permet de vérifier la structure d'un schéma via "schema checks" et propose l'auto-complétion de champs (sous liscence MIT).

https://www.apollographql.com/docs/graphos/

- GraphiQL : Fait de l'introspection pour récupérer la documentation de notre API, propose également l'auto-complétion de champs (sous liscence MIT).

https://github.com/graphql/graphiql/blob/main/packages/graphiql/README.md

- GraphQL-playground : IDE GraphQL interactif développé par Prisma et basé sur GraphiQL, (sous liscence MIT). 

https://github.com/graphql/graphql-playground

Courbe d'apprentissage
- REST possède une grande source de documentation, de nombreux outils et resources disponibles. 
- GraphQL possède lui moins de ressources mais on retrouve tout de même le forum apollo dédié à la discussion sur GraphQL, ainsi que Apollo GraphOS.

Lien de la communauté apollo :

https://community.apollographql.com/
https://www.apollographql.com/docs/graphos/

Téléchargement des fichiers 
- Le téléchargement de fichier n'est pas pris en compte par GraphQL, il faudra trouver une autre solution (la librairie graphql-upload).


https://github.com/lmcgartland/graphene-file-upload

Documentation 
- Pour GraphQL, on peut utiliser différents outils tel que dociql ou spectaql qui génère une documentattion dans un répertoire séparé "public".

![Capture d’écran du 2024-03-07 16-38-01.png](..%2F..%2F..%2F..%2FImages%2FCaptures%20d%E2%80%99%C3%A9cran%2FCapture%20d%E2%80%99%C3%A9cran%20du%202024-03-07%2016-38-01.png)

Dociql permet de générer :
- des exemples de requête/réponse avec l'option "Try it now".
- des exemples de schémas.

Message d'erreur
- GraphQL à introduit des tableaux d'erreurs en options pour faire face à la non pertinence des codes d'erreurs HTTP. Exemple : Plusieurs opérations envoyer dans la même requête, mais il est impossible qu'une requête échoue partiellement, renvoyant ainsi des données erronées et réelles.

Exemple d'erreur
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

Autre exemple d'erreur 
``` bash 
{
  "errors": [
    {
      "message": "Name for character with ID 1002 could not be fetched.",
      "locations": [ { "line": 6, "column": 7 } ],
      "path": [ "hero", "heroFriends", 1, "name" ]
    }
  ],
  "data": {
    "hero": {
      "name": "R2-D2",
      "heroFriends": [
        {
          "id": "1000",
          "name": "Luke Skywalker"
        },
        {
          "id": "1002",
          "name": null
        },
        {
          "id": "1003",
          "name": "Leia Organa"
        }
      ]
    }
  }
}
```
Performance 
- GraphQl a une absence de prise en charge native de la mise en cache, on doit mettre en oeuvre des stratégies de cache personnalisées.
- Attention, lorsque des requêtes GraphQL deviennent excesivement complexes et imbriquées, cela peut entraîner une surcharge significative sur le serveur.
- REST utilise les pratiques standard de mise en cache HTTP.

Sécurité
- Pour faire en oeuvre des mécanismes d'authentification on peut notamment utiliser OSO (l'autorisation intervient à différents moments).


https://www.osohq.com/post/graphql-authorization

Différentes librairies GraphQL (python) entre graphene, strawberry et Ariadne :

| Language| Schema-first implementation | Code-first implementation |
|---------|:---------------------------:|:-------------------------:|
| Python  |           Ariadne           |   Graphene / Strawberry   |

Lien comparatif : 

https://www.libhunt.com/compare-graphene-vs-strawberry
https://graphql.org/code/#python

Exemple d'application Flask avec GraphQL :

https://github.com/graphql-python/graphql-server/blob/master/docs/flask.md

## Besoin du projet
Iris étant en train de s'agrandir et d'être utilisé par de plus en plus en plus d'utilisateurs un objectif majeur, serait de faciliter la gestion d'un grand nombre de requêtes. 
Exemple : Récupération des données liées aux cases.

- GraphQL permettrai d'éviter cette sur-récupération de données.

## Les risques encourus 
- Inconnue MFA 
- Recul technologique 
- Un grand nombre de données inconnues sur GraphQL (haut risque)

## Conclusion
Etant donné le contexte actuel, il a été décidé de partir sur GraphQL.
Cela représente plus de travail pour reprendre toute l'API depuis le début mais à terme l'api supportera plus facilement un plus grand nombre de données.
Un exemple typique de l'avantage de GraphQL, sera la récupération de métadonnée sur un case.

