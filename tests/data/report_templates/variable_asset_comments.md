{% for asset in assets %}
{% for comment in asset.comments %}
{{ comment.comment_text }}
{% endfor %}
{% endfor %}
