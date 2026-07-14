{% for ioc in iocs %}
{% for comment in ioc.comments %}
{{ comment.comment_text }}
{% endfor %}
{% endfor %}
