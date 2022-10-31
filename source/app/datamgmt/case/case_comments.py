from app.models import Comments


def get_case_comment(comment_id, caseid):
    return Comments.query.filter(
        Comments.comment_id == comment_id,
        Comments.comment_case_id == caseid
    ).first()
