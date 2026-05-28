CONSTRAINTS = [
    "CREATE CONSTRAINT company_id IF NOT EXISTS FOR (n:Company) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT institution_id IF NOT EXISTS FOR (n:Institution) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (n:Person) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT event_id IF NOT EXISTS FOR (n:Event) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (n:Document) REQUIRE n.id IS UNIQUE",
    "CREATE INDEX company_name IF NOT EXISTS FOR (n:Company) ON (n.name)",
    "CREATE INDEX institution_name IF NOT EXISTS FOR (n:Institution) ON (n.name)",
]
