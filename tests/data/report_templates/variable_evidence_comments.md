{% for evidence in evidences %}
{% for comment in evidence.comments %}
{{ comment.comment_text }}
{% endfor %}
{% endfor %}
