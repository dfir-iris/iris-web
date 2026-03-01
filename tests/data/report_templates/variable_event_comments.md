{% for event in timeline %}
{% for comment in event.comments %}
{{ comment.comment_text }}
{% endfor %}
{% endfor %}
