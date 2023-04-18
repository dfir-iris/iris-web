from app.models import SavedFilter


def get_filter_by_id(filter_id):
    """
    Get a filter by its ID

    args:
        filter_id: the ID of the filter to get

    returns:
        SavedFilter object
    """
    return SavedFilter.query.filter(SavedFilter.filter_id == filter_id).first()


def list_filters_by_type(filter_type):
    """
    List filters by type

    args:
        filter_type: the type of filter to list

    returns:
        List of SavedFilter objects
    """
    return SavedFilter.query.filter(SavedFilter.filter_type == filter_type).all()
