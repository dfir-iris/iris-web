{% for task in tasks %}
{% for comment in task.comments %}
{{ comment.comment_text }}
{% endfor %}
{% endfor %}
