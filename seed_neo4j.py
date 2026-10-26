"""
Seed Northwind Dataset into Neo4j Database.

Connects to a Neo4j database and populates it with the standard Northwind
graph dataset (Customers, Products, Categories, Suppliers, Employees, Orders)
using LOAD CSV from https://data.neo4j.com/northwind/.
"""

import os
import sys
import time

# Ensure official neo4j driver is imported cleanly without directory shadowing
current_dir = os.path.dirname(os.path.abspath(__file__))
try:
    from neo4j import GraphDatabase
except ImportError:
    import importlib.machinery, importlib.util
    search_paths = [p for p in sys.path if os.path.abspath(p) not in (current_dir, "")]
    spec = importlib.machinery.PathFinder.find_spec('neo4j', search_paths)
    if spec:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        GraphDatabase = getattr(mod, "GraphDatabase")
    else:
        raise

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(current_dir, ".env"))
except ImportError:
    pass

# ==============================================================================
# Connection Credentials (Edit these variables or configure in .env)
# ==============================================================================
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")  # <-- Change this to your local password
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

CSV_BASE_URL = "https://data.neo4j.com/northwind"


# ==============================================================================
# Seeding Cypher Commands
# ==============================================================================
CONSTRAINTS = [
    ("Customer ID uniqueness", "CREATE CONSTRAINT customer_id IF NOT EXISTS FOR (c:Customer) REQUIRE c.customerID IS UNIQUE"),
    ("Product ID uniqueness", "CREATE CONSTRAINT product_id IF NOT EXISTS FOR (p:Product) REQUIRE p.productID IS UNIQUE"),
    ("Category ID uniqueness", "CREATE CONSTRAINT category_id IF NOT EXISTS FOR (c:Category) REQUIRE c.categoryID IS UNIQUE"),
    ("Supplier ID uniqueness", "CREATE CONSTRAINT supplier_id IF NOT EXISTS FOR (s:Supplier) REQUIRE s.supplierID IS UNIQUE"),
    ("Employee ID uniqueness", "CREATE CONSTRAINT employee_id IF NOT EXISTS FOR (e:Employee) REQUIRE e.employeeID IS UNIQUE"),
    ("Order ID uniqueness", "CREATE CONSTRAINT order_id IF NOT EXISTS FOR (o:Order) REQUIRE o.orderID IS UNIQUE")
]

NODE_LOADERS = [
    (
        "Loading Categories",
        f"""
        LOAD CSV WITH HEADERS FROM '{CSV_BASE_URL}/categories.csv' AS row
        MERGE (c:Category {{categoryID: row.categoryID}})
        ON CREATE SET c.categoryName = row.categoryName,
                      c.description = row.description
        """
    ),
    (
        "Loading Suppliers",
        f"""
        LOAD CSV WITH HEADERS FROM '{CSV_BASE_URL}/suppliers.csv' AS row
        MERGE (s:Supplier {{supplierID: row.supplierID}})
        ON CREATE SET s.companyName = row.companyName,
                      s.contactName = row.contactName,
                      s.contactTitle = row.contactTitle,
                      s.address = row.address,
                      s.city = row.city,
                      s.region = row.region,
                      s.postalCode = row.postalCode,
                      s.country = row.country,
                      s.phone = row.phone,
                      s.fax = row.fax,
                      s.contact_email = toLower(replace(row.contactName, ' ', '.')) + '@' + toLower(replace(replace(row.companyName, ' ', ''), ',', '')) + '.com'
        """
    ),
    (
        "Loading Products",
        f"""
        LOAD CSV WITH HEADERS FROM '{CSV_BASE_URL}/products.csv' AS row
        MERGE (p:Product {{productID: row.productID}})
        ON CREATE SET p.productName = row.productName,
                      p.supplierID = row.supplierID,
                      p.categoryID = row.categoryID,
                      p.quantityPerUnit = row.quantityPerUnit,
                      p.unitPrice = toFloat(row.unitPrice),
                      p.unitsInStock = toInteger(row.unitsInStock),
                      p.unitsOnOrder = toInteger(row.unitsOnOrder),
                      p.reorderLevel = toInteger(row.reorderLevel),
                      p.discontinued = (row.discontinued = '1')
        """
    ),
    (
        "Loading Employees",
        f"""
        LOAD CSV WITH HEADERS FROM '{CSV_BASE_URL}/employees.csv' AS row
        MERGE (e:Employee {{employeeID: row.employeeID}})
        ON CREATE SET e.firstName = row.firstName,
                      e.lastName = row.lastName,
                      e.title = row.title,
                      e.titleOfCourtesy = row.titleOfCourtesy,
                      e.birthDate = row.birthDate,
                      e.hireDate = row.hireDate,
                      e.address = row.address,
                      e.city = row.city,
                      e.region = row.region,
                      e.postalCode = row.postalCode,
                      e.country = row.country,
                      e.homePhone = row.homePhone,
                      e.extension = row.extension,
                      e.reportsTo = row.reportsTo,
                      e.email = toLower(row.firstName) + '.' + toLower(row.lastName) + '@northwind.com'
        """
    ),
    (
        "Loading Customers",
        f"""
        LOAD CSV WITH HEADERS FROM '{CSV_BASE_URL}/customers.csv' AS row
        MERGE (c:Customer {{customerID: row.customerID}})
        ON CREATE SET c.companyName = row.companyName,
                      c.contactName = row.contactName,
                      c.contactTitle = row.contactTitle,
                      c.address = row.address,
                      c.city = row.city,
                      c.region = row.region,
                      c.postalCode = row.postalCode,
                      c.country = row.country,
                      c.phone = row.phone,
                      c.fax = row.fax
        """
    ),
    (
        "Loading Orders",
        f"""
        LOAD CSV WITH HEADERS FROM '{CSV_BASE_URL}/orders.csv' AS row
        MERGE (o:Order {{orderID: row.orderID}})
        ON CREATE SET o.orderDate = row.orderDate,
                      o.requiredDate = row.requiredDate,
                      o.shippedDate = row.shippedDate,
                      o.shipVia = row.shipVia,
                      o.freight = row.freight,
                      o.shipName = row.shipName,
                      o.shipAddress = row.shipAddress,
                      o.shipCity = row.shipCity,
                      o.shipRegion = row.shipRegion,
                      o.shipPostalCode = row.shipPostalCode,
                      o.shipCountry = row.shipCountry,
                      o.customerID = row.customerID,
                      o.employeeID = row.employeeID
        """
    )
]

RELATIONSHIP_LOADERS = [
    (
        "Creating (:Product)-[:PART_OF]->(:Category) relationships",
        f"""
        LOAD CSV WITH HEADERS FROM '{CSV_BASE_URL}/products.csv' AS row
        MATCH (p:Product {{productID: row.productID}})
        MATCH (c:Category {{categoryID: row.categoryID}})
        MERGE (p)-[:PART_OF]->(c)
        """
    ),
    (
        "Creating (:Supplier)-[:SUPPLIES]->(:Product) relationships",
        f"""
        LOAD CSV WITH HEADERS FROM '{CSV_BASE_URL}/products.csv' AS row
        MATCH (s:Supplier {{supplierID: row.supplierID}})
        MATCH (p:Product {{productID: row.productID}})
        MERGE (s)-[:SUPPLIES]->(p)
        """
    ),
    (
        "Creating (:Employee)-[:REPORTS_TO]->(:Employee) relationships",
        f"""
        LOAD CSV WITH HEADERS FROM '{CSV_BASE_URL}/employees.csv' AS row
        WHERE row.reportsTo IS NOT NULL AND row.reportsTo <> ''
        MATCH (e:Employee {{employeeID: row.employeeID}})
        MATCH (m:Employee {{employeeID: row.reportsTo}})
        MERGE (e)-[:REPORTS_TO]->(m)
        """
    ),
    (
        "Creating (:Customer)-[:PURCHASED]->(:Order) relationships",
        f"""
        LOAD CSV WITH HEADERS FROM '{CSV_BASE_URL}/orders.csv' AS row
        MATCH (c:Customer {{customerID: row.customerID}})
        MATCH (o:Order {{orderID: row.orderID}})
        MERGE (c)-[:PURCHASED]->(o)
        """
    ),
    (
        "Creating (:Order)-[:ORDERS]->(:Product) line-item relationships",
        f"""
        LOAD CSV WITH HEADERS FROM '{CSV_BASE_URL}/order-details.csv' AS row
        MATCH (o:Order {{orderID: row.orderID}})
        MATCH (p:Product {{productID: row.productID}})
        MERGE (o)-[r:ORDERS]->(p)
        ON CREATE SET r.unitPrice = row.unitPrice,
                      r.quantity = toInteger(row.quantity),
                      r.discount = row.discount
        """
    )
]


# ==============================================================================
# Seeding Runner
# ==============================================================================
def seed_database():
    """Connects to Neo4j and runs the Northwind dataset seeding pipeline."""
    print("=" * 70)
    print("        NEO4J NORTHWIND DATASET SEEDING SCRIPT")
    print("=" * 70)
    print(f"\n[*] Connecting to Neo4j:")
    print(f"    URI:      {NEO4J_URI}")
    print(f"    User:     {NEO4J_USER}")
    print(f"    Database: {NEO4J_DATABASE}")

    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        print("    [OK] Successfully connected to Neo4j instance!")
    except Exception as e:
        print(f"\n[ERROR] Connection failed: {e}")
        print("\nPlease check your NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD settings")
        print("at the top of this script or in your .env file.")
        return

    t_start = time.time()

    with driver.session(database=NEO4J_DATABASE) as session:
        # Step 1: Constraints / Indexes
        print("\n[1/3] Creating Unique Constraints & Indexes...")
        for desc, stmt in CONSTRAINTS:
            try:
                session.run(stmt)
                print(f"    [OK] {desc}")
            except Exception as e:
                # If constraint exists or older syntax required, print notice
                print(f"    [NOTE] {desc}: {e}")

        # Step 2: Load Nodes
        print("\n[2/3] Loading Nodes from Public Northwind CSVs...")
        for label, stmt in NODE_LOADERS:
            t0 = time.time()
            print(f"    [*] {label}...", end="", flush=True)
            try:
                session.run(stmt)
                print(f" Done ({time.time() - t0:.2f}s)")
            except Exception as e:
                print(f" FAILED: {e}")

        # Step 3: Load Relationships
        print("\n[3/3] Creating Graph Relationships & Edges...")
        for label, stmt in RELATIONSHIP_LOADERS:
            t0 = time.time()
            print(f"    [*] {label}...", end="", flush=True)
            try:
                session.run(stmt)
                print(f" Done ({time.time() - t0:.2f}s)")
            except Exception as e:
                print(f" FAILED: {e}")

        # Step 4: Verification Summary
        print("\n" + "=" * 70)
        print("VERIFICATION: Populated Graph Counts")
        print("=" * 70)
        
        node_counts = session.run("""
            MATCH (n)
            RETURN labels(n)[0] AS Label, count(n) AS Count
            ORDER BY Count DESC
        """)
        print("\nNode Counts:")
        for record in node_counts:
            print(f"  - (:{record['Label']}): {record['Count']} nodes")

        rel_counts = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) AS Relationship, count(r) AS Count
            ORDER BY Count DESC
        """)
        print("\nRelationship Counts:")
        for record in rel_counts:
            print(f"  - [:{record['Relationship']}]: {record['Count']} edges")

    driver.close()
    total_time = time.time() - t_start
    print(f"\n[SUCCESS] Neo4j Northwind dataset seeding completed in {total_time:.2f}s!\n")


if __name__ == "__main__":
    seed_database()
