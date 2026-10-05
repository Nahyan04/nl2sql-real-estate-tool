from app.api.routes.examples import load_examples
from app.services.sales_query_plans import sales_analysis_plan
from app.services.rental_query_plans import source_rental_plan
from app.services.sql_validator import validate_product_query


def test_gallery_examples_have_supported_topics_and_safe_source_plans():
    examples = load_examples().examples
    assert len({example.id for example in examples}) == len(examples)
    for lang in ('en', 'ar'):
        assert len([example for example in examples if example.lang == lang and example.featured]) == 3
    for example in examples:
        assert example.title and example.topic in ('sales', 'leasing', 'trends')
        sales = sales_analysis_plan(example.text)
        rental = source_rental_plan(example.text)
        assert sales or rental
        assert validate_product_query(sales[0] if sales else rental.sql).is_safe
        assert 'yield' not in example.text.lower()
