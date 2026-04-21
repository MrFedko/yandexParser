from data.dataclasses import Review
from loader import data_base


def message_builder(review: Review) -> str:
    rest_name = data_base.get_rest_name_by_id(review.rest_id)
    rating = {1: '★✩✩✩✩',
              2: '★★✩✩✩',
              3: '★★★✩✩',
              4: '★★★★✩',
              5: '★★★★★'}
    review_author = f'<a href="{review.author_url}">{review.author_name}</a>'
    message = f'''
    {rest_name["rest_name"]}
    {rating[review.rating]}
    {review.date_time}
    автор: {review_author}

    {review.text}'''
    return message
