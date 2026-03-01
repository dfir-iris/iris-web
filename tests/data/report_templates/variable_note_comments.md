{% for note in notes %}
{% for comment in note.comments %}
{{ comment.comment_text }}
{% endfor %}
{% endfor %}
