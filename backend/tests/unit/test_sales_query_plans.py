from app.services.sales_query_plans import sales_analysis_plan, render_sales_analysis
from app.services.sql_validator import validate_product_query


def test_explicit_bateen_source_district_does_not_require_municipality():
    question = "What was the exported sales value in the Al Bateen source district in 2025, across all municipalities?"
    plan = sales_analysis_plan(question)
    assert plan and plan[1] == "district_value"
    assert "district = 'Al Bateen'" in plan[0]
    assert validate_product_query(plan[0]).is_safe


def test_unqualified_top_district_ranking_does_not_gain_residential_filter():
    for question in (
        "Which five source districts had the highest exported sales value in 2025?",
        "ما المناطق المصدرية الخمس الأعلى من حيث قيمة المبيعات الواردة في بيانات عام 2025؟",
    ):
        plan = sales_analysis_plan(question)
        assert plan and plan[1] == "top_districts"
        assert "asset_class" not in plan[0]
        assert "LIMIT 5" in plan[0]
        assert validate_product_query(plan[0]).is_safe
    assert sales_analysis_plan("Which five source districts had the highest residential sales value in 2025?") is None


def test_sale_type_plans_report_source_categories_without_causes():
    value_question = "Compare exported sales value by source sale type in 2025."
    count_question = "قارن عدد سجلات البيع على الخارطة والجاهز في عام 2025."
    value_plan = sales_analysis_plan(value_question)
    count_plan = sales_analysis_plan(count_question)
    assert value_plan and value_plan[1] == "sale_type_value"
    assert count_plan and count_plan[1] == "sale_type_count"
    assert "sale_type IN ('off-plan', 'ready')" in count_plan[0]
    assert all(validate_product_query(plan[0]).is_safe for plan in (value_plan, count_plan))
    answer = render_sales_analysis(value_question, value_plan[1], [["off-plan", 100], ["ready", 50]], "en")
    assert "off-plan" in answer and "ready" in answer
    assert "premium" not in answer and "larger" not in answer
    example = sales_analysis_plan("Compare off-plan, ready and court-mandated sales value in 2025.")
    assert example and example[1] == "sale_type_value"
    assert "sale_type IN ('off-plan', 'ready', 'court-mandated')" in example[0]
    assert sales_analysis_plan("Compare exported sales value by source sale type in Al Reem Island in 2025.") is None
    assert sales_analysis_plan("قارن عدد سجلات البيع على الخارطة والجاهز في المنطقة المصدرية Al Reem Island عام 2025.") is None


def test_plain_year_count_and_value_include_zero_count_period():
    cases = [
        ("How many sales observations are in the export for 2025?", "year_count"),
        ("كم عدد سجلات المبيعات الواردة في البيانات لعام 2030؟", "year_count"),
        ("What was the total exported sales value in AED in 2025?", "year_value"),
    ]
    for question, kind in cases:
        plan = sales_analysis_plan(question)
        assert plan and plan[1] == kind
        assert validate_product_query(plan[0]).is_safe
    answer = render_sales_analysis(cases[1][0], "year_count", [[0]], "ar")
    assert "0" in answer and "2030" in answer
    assert sales_analysis_plan("How many residential sales observations are in the export for 2025?") is None
    assert sales_analysis_plan("What was the total exported sales value in Yas Island in 2025?") is None
