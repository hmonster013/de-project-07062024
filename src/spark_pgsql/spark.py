"""
Spark Application
"""
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.types import StructType, StructField, StringType
from pyspark.sql.functions import from_json, col, concat_ws, lit, split, udf
from unidecode import unidecode
import re

RAW_COLUMNS = [
	"reference_fiche",
	"ndeg_de_version",
	"nature_juridique_du_rappel",
	"categorie_de_produit",
	"sous_categorie_de_produit",
	"nom_de_la_marque_du_produit",
	"noms_des_modeles_ou_references",
	"identification_des_produits",
	"conditionnements",
	"date_debut_fin_de_commercialisation",
	"temperature_de_conservation",
	"marque_de_salubrite",
	"informations_complementaires",
	"zone_geographique_de_vente",
	"distributeurs",
	"motif_du_rappel",
	"risques_encourus_par_le_consommateur",
	"preconisations_sanitaires",
	"description_complementaire_du_risque",
	"conduites_a_tenir_par_le_consommateur",
	"numero_de_contact",
	"modalites_de_compensation",
	"date_de_fin_de_la_procedure_de_rappel",
	"informations_complementaires_publiques",
	"liens_vers_les_images",
	"lien_vers_la_liste_des_produits",
	"lien_vers_la_liste_des_distributeurs",
	"lien_vers_affichette_pdf",
	"lien_vers_la_fiche_rappel",
	"rappelguid",
	"date_de_publication",
]

COLUMNS_TO_NORMALIZE = [
    "categorie_de_produit",
    "sous_categorie_de_produit",
    "nom_de_la_marque_du_produit",
    "noms_des_modeles_ou_references",
    "identification_des_produits",
    "conditionnements",
    "temperature_de_conservation",
    "zone_geographique_de_vente",
    "distributeurs",
    "motif_du_rappel",
    "numero_de_contact",
    "modalites_de_compensation",
]

COLUMNS_TO_KEEP = [
    "reference_fiche",
    "liens_vers_les_images",
    "lien_vers_la_liste_des_produits",
    "lien_vers_la_liste_des_distributeurs",
    "lien_vers_affichette_pdf",
    "lien_vers_la_fiche_rappel",
    "date_de_publication",
    "date_de_fin_de_la_procedure_de_rappel",
]

def create_spark_connection():
    """ Creating spark connection

    Returns:
        spark: SparkSession
    """
    spark_conn = SparkSession \
        .builder \
        .appName("RappelConso Spark") \
        .config("spark.streaming.stopGracefullyOnShutdown", True) \
        .config("spark.jars.packages",
                "org.postgresql:postgresql:42.7.3, \
                org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1") \
        .getOrCreate()

    return spark_conn

def create_df_from_kafka(spark_conn):
    """Create data frame from kafka

    Args:
        spark (SparkSession): 

    Returns:
        exploded_df: data frame
    """
    streaming_df = spark_conn.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9094") \
    .option("subscribe", "test") \
    .option("startingOffsets", "earliest") \
    .load()

    json_schema = StructType([StructField(field, StringType(), True) for field in RAW_COLUMNS])

    json_df = streaming_df.select(from_json(col("value").cast("string"), schema=json_schema)
                                  .alias("value"))

    exploded_df = json_df.selectExpr("value.*")

    return exploded_df

def merge_two_columns(
        col_a: str, col_b: str, col_merge: str, df: DataFrame
) -> DataFrame:
    """ Merge two columns

    Args:
        col_a (str): Column name
        col_b (str): Column name
        col_merge (str): Column name
        row (DataFrame): Raw data

    Returns:
        DataFrame: Transform data
    """
    final = df \
        .withColumn(col_merge, concat_ws("\n", col_a, col_b)) \
        .drop(col_a) \
        .drop(col_b)

    return final

def separate_commercialisation_dates(df: DataFrame) -> DataFrame:
    """Split Date

    Args:
        df (dict): Raw data

    Returns:
        DataFrame: Transform data
    """
    split_col = split(df["date_debut_fin_de_commercialisation"], " ")

    df_result = df.withColumn("date_debut_commercialisation", split_col.getItem(1)) \
                   .withColumn("date_fin_commercialisation", split_col.getItem(3)) \
                   .drop("date_debut_fin_de_commercialisation")

    return df_result

def normalize_one(text: str) -> str:
    """
    Remove accents.
    """
    if text is not None:
        return unidecode(text.strip().lower())
    return text

def normalize_columns(df: DataFrame) -> DataFrame:
    """ Normalize columns

    Args:
        df (DataFrame): Raw data

    Returns:
        DataFrame: Transform data
    """
    normalize_udf = udf(normalize_one, StringType())
    for col_name in COLUMNS_TO_NORMALIZE:
        df = df.withColumn(col_name, normalize_udf(df[col_name]))

    return df

def transform(df):
    """ Transform   

    Args:
        df (DataFrame): Raw data

    Returns:
        DataFrame: Transform data
    """
    df = df.drop("ndeg_de_version") \
        .drop("rappelguid") \
        .drop("nature_juridique_du_rappel") \
        .drop("marque_de_salubrite")
    
    df = normalize_columns(df)

    df = merge_two_columns(
        "risques_encourus_par_le_consommateur",
        "description_complementaire_du_risque",
        "risques_pour_le_consommateur",
        df,
    )

    df = merge_two_columns(
        "preconisations_sanitaires",
        "conduites_a_tenir_par_le_consommateur",
        "recommandations_sante",
        df,
    )

    df = merge_two_columns(
        "informations_complementaires",
        "informations_complementaires_publiques",
        "informations_complementaires",
        df,
    )

    df = separate_commercialisation_dates(df)

    return df

def save_to_postgres(batch_df, batch_id):
    """ Save data to postgres

    Args:
        batch_df (data frame): 
        batch_id (_type_): _description_
    """
    batch_df.write \
        .mode('append') \
        .format("jdbc") \
        .option("url", f"jdbc:postgresql://postgresql:5432/postgres") \
        .option("driver", "org.postgresql.Driver") \
        .option("dbtable", 'rappel_conso_table') \
        .option("user", 'postgres') \
        .option("password", 'postgres') \
        .save()

if __name__ == "__main__":
    spark_conn = create_spark_connection()
    df = create_df_from_kafka(spark_conn=spark_conn)
    df = transform(df=df)
    query = df.writeStream \
        .outputMode("append") \
        .foreachBatch(save_to_postgres) \
        .option("checkpointLocation", ".\\data\\chk-point-dir") \
        .trigger(processingTime="1 minute") \
        .start() \
        .awaitTermination()
