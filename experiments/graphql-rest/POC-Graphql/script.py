import requests


url = 'http://127.0.0.1:5000/graphql-api'
query = 'query{ allMovies { edges { node { title description}}}}'
r = requests.post(url, json={'query': query})
print("Voici la réponse de le requête 1 :")
print(r.text)

query2 = 'query{ allBooks { edges{ node { title description author { username }}}}}'
r2 = requests.post(url, json={'query': query2})
print("Voici la réponse de le requête 2:")
print(r2.text)

query3 = 'mutation{ addBook( username:"mikedean", title:"Graphql", description : "V1", year:2018) { book { title }}}'
r3 = requests.post(url, json={'query': query3})
print("Voici la réponse de le requête 3:")
print(r3.text)
