from psycopg2 import extras
from psycopg2 import DatabaseError
from pathlib import Path
import psycopg2
import logging
import numpy as np
import uuid
from datetime import datetime

from .config import GenerateConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Database:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance.db_config = GenerateConfig.config()
        return cls._instance

    def __enter__(self):
        self.conn = psycopg2.connect(**self.db_config)
        self.cursor = self.conn.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()

    def initialize_tables(self):
        sql_path = Path(__file__).resolve().parent / "sql" / "table_initialize.sql"
        with sql_path.open("r") as file:
            query = file.read()
        try:
            self.cursor.execute(query)
            self.conn.commit()
        except DatabaseError as e:
            self.conn.rollback()
            raise e

    def reset_database(self):
        sql_path = Path(__file__).resolve().parent / "sql" / "database_reset.sql"
        with sql_path.open("r") as file:
            query = file.read()
        try:
            self.cursor.execute(query)
            self.conn.commit()
        except DatabaseError as e:
            self.conn.rollback()
            raise e

    def _bytes_to_embeddings(self, byte_array):
        return np.frombuffer(byte_array.tobytes(), dtype=np.float16).reshape(
            byte_array.shape[0], -1
        )

    def get_user_info_w_email(self, user_email: str):
        query_get_user_info = """
        SELECT DISTINCT user_id, user_name, user_surname, user_password, user_type, is_active, user_created_at
        FROM user_info
        WHERE user_email = %s
        """
        try:
            self.cursor.execute(query_get_user_info, (user_email,))
            data = self.cursor.fetchone()
            return (
                {
                    "user_id": data[0],
                    "user_name": data[1],
                    "user_surname": data[2],
                    "user_password": data[3],
                    "user_type": data[4],
                    "is_active": data[5],
                    "user_created_at": str(data[6]),
                }
                if data
                else None
            )
        except DatabaseError as e:
            self.conn.rollback()
            raise e

    def get_user_info_w_id(self, user_id: str):
        query_get_user_info = """
        SELECT DISTINCT user_name, user_surname, user_email, user_type, user_created_at
        FROM user_info
        WHERE user_id = %s
        """
        query_get_domain_ids = """
        SELECT DISTINCT domain_id
        FROM domain_info
        WHERE user_id = %s
        """
        query_get_domain_info = """
        SELECT t1.domain_name, t1.domain_id, t2.file_name, t2.file_id
        FROM domain_info t1
        LEFT JOIN file_info t2 ON t1.domain_id = t2.domain_id
        WHERE t1.domain_id IN %s
        """

        try:
            self.cursor.execute(query_get_user_info, (user_id,))
            user_info_data = self.cursor.fetchone()

            if not user_info_data:
                return None, None

            user_info = {
                "user_name": user_info_data[0],
                "user_surname": user_info_data[1],
                "user_email": user_info_data[2],
                "user_type": user_info_data[3],
                "user_created_at": str(user_info_data[4]),
            }

            self.cursor.execute(query_get_domain_ids, (user_id,))
            domain_id_data = self.cursor.fetchall()

            if not domain_id_data:
                return user_info, None

            domain_ids = [data[0] for data in domain_id_data]
            self.cursor.execute(query_get_domain_info, (tuple(domain_ids),))
            domain_info_data = self.cursor.fetchall()
            domain_info = {}
            for data in domain_info_data:
                if data[1] not in domain_info.keys():
                    domain_info[data[1]] = {
                        "domain_name": data[0],
                        "file_names": [data[2]] if data[2] else [],
                        "file_ids": [data[3]] if data[3] else [],
                    }
                else:
                    domain_info[data[1]]["file_names"].append(data[2])
                    domain_info[data[1]]["file_ids"].append(data[3])

            return user_info, domain_info

        except DatabaseError as e:
            self.conn.rollback()
            raise e

    def get_file_info_with_domain(self, user_id: str, domain_id: str):
        query_get_file_info = """
        SELECT DISTINCT file_id, file_name, file_modified_date, file_upload_date
        FROM file_info
        WHERE user_id = %s AND domain_id = %s
        """
        try:
            self.cursor.execute(
                query_get_file_info,
                (
                    user_id,
                    domain_id,
                ),
            )
            data = self.cursor.fetchall()
            return (
                [
                    {
                        "file_id": row[0],
                        "file_name": row[1],
                        "file_modified_date": row[2],
                        "file_upload_date": row[3],
                    }
                    for row in data
                ]
                if data
                else None
            )
        except DatabaseError as e:
            self.conn.rollback()
            raise e

    def get_domain_info(self, user_id: str, domain_id: int):
        query = """
        SELECT DISTINCT domain_name
        FROM domain_info
        WHERE user_id = %s AND domain_id = %s
        """
        try:
            self.cursor.execute(
                query,
                (
                    user_id,
                    domain_id,
                ),
            )
            data = self.cursor.fetchone()
            return {"domain_name": data[0]} if data else None
        except DatabaseError as e:
            self.conn.rollback()
            raise e

    def get_file_content(self, file_ids: list):
        query_get_content = """
        SELECT t1.sentence AS sentence, t1.is_header AS is_header, t1.is_table AS is_table, t1.page_number AS page_number, t1.file_id AS file_id, t2.file_name AS file_name
        FROM file_content t1
        LEFT JOIN file_info t2 ON t1.file_id = t2.file_id
        WHERE t1.file_id IN %s
        """
        query_get_embeddings = """
        SELECT array_agg(embedding) AS embeddings
        FROM file_content
        WHERE file_id IN %s
        """
        try:
            self.cursor.execute(query_get_content, (tuple(file_ids),))
            content = self.cursor.fetchall()
            self.cursor.execute(query_get_embeddings, (tuple(file_ids),))
            byte_embeddings = self.cursor.fetchone()
            if content and byte_embeddings and byte_embeddings[0]:
                embeddings = self._bytes_to_embeddings(np.array(byte_embeddings[0]))
                return content, embeddings
            else:
                return None, None
        except DatabaseError as e:
            self.conn.rollback()
            print(f"Database error occurred: {e}")
            return None, None
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return None, None

    def get_session_info(self, session_id: str):
        query_get_session = """
        SELECT user_id, created_at
        FROM session_info
        WHERE session_id = %s
        """
        self.cursor.execute(query_get_session, (session_id,))
        data = self.cursor.fetchone()
        return {"user_id": data[0], "created_at": data[1]} if data else None

    def rename_domain(self, domain_id: str, new_name: str):
        query = """
        UPDATE domain_info 
        SET domain_name = %s
        WHERE domain_id = %s
        """
        try:
            self.cursor.execute(query, (new_name, domain_id))
            rows_affected = self.cursor.rowcount
            return rows_affected > 0
        except DatabaseError as e:
            self.conn.rollback()
            raise e

    def insert_user_guide(self, user_id: str, domain_id: str):
        """
        Insert default user guide content into user's default domain
        """
        file_id = str(uuid.uuid4())
        current_date = datetime.now().date()

        # Insert file info
        query_insert_file_info = """
        INSERT INTO file_info 
            (user_id, domain_id, file_id, file_name, file_modified_date, file_upload_date)
        VALUES 
            (%s, %s, %s, %s, %s, %s)
        """

        # Copy content from default_content to file_content
        query_insert_file_content = """
        INSERT INTO file_content 
            (file_id, sentence, is_header, is_table, page_number, embedding)
        SELECT 
            %s,
            sentence,
            is_header,
            is_table,
            page_number,
            embedding
        FROM default_content
        """

        try:
            # Insert file info
            self.cursor.execute(
                query_insert_file_info,
                (
                    user_id,
                    domain_id,
                    file_id,
                    "User Guide.pdf",
                    current_date,
                    current_date,
                ),
            )

            # Insert file content
            self.cursor.execute(query_insert_file_content, (file_id,))
            return

        except DatabaseError as e:
            self.conn.rollback()
            logger.error(f"Error inserting user guide: {str(e)}")
            raise e

    def delete_domain(self, domain_id: str):
        get_domain_type_query = """
        SELECT domain_type
        FROM domain_info
        WHERE domain_id = %s
        """
        get_files_query = """
        SELECT file_id 
        FROM file_info 
        WHERE domain_id = %s
        """

        delete_content_query = """
        DELETE FROM file_content 
        WHERE file_id IN %s
        """

        delete_files_query = """
        DELETE FROM file_info 
        WHERE domain_id = %s
        """

        delete_domain_query = """
        DELETE FROM domain_info 
        WHERE domain_id = %s
        """

        try:
            self.cursor.execute(get_domain_type_query, (domain_id,))
            domain_type = self.cursor.fetchone()
            if not domain_type[0]:
                return -1

            self.cursor.execute(get_files_query, (domain_id,))
            file_data = self.cursor.fetchall()
            file_ids = [data[0] for data in file_data]

            # content -> files -> domain
            if file_ids:
                self.cursor.execute(delete_content_query, (tuple(file_ids),))
            self.cursor.execute(delete_files_query, (domain_id,))
            self.cursor.execute(delete_domain_query, (domain_id,))

            rows_affected = self.cursor.rowcount

            return 1 if rows_affected else 0

        except DatabaseError as e:
            # Rollback in case of error
            self.cursor.execute("ROLLBACK")
            logger.error(f"Error deleting domain {domain_id}: {str(e)}")
            raise e

    def insert_user_info(
        self,
        user_id: str,
        google_id: str,
        user_name: str,
        user_surname: str,
        user_password: str,
        user_email: str,
        picture_url: str,
        refresh_token: str,
        access_token: str,
        user_type: str,
        is_active: bool,
    ):
        query = """
        INSERT INTO user_info (
            user_id, google_id, user_name, user_surname, user_password,
            user_email, picture_url, refresh_token, access_token,
            user_type, is_active
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        try:
            self.cursor.execute(
                query,
                (
                    user_id,
                    google_id,
                    user_name,
                    user_surname,
                    user_password,
                    user_email,
                    picture_url,
                    refresh_token,
                    access_token,
                    user_type,
                    is_active,
                ),
            )
        except DatabaseError as e:
            self.conn.rollback()
            raise e

    def insert_user_feedback(
        self,
        feedback_id: str,
        user_id: str,
        feedback_type: str,
        description: str,
        screenshot: str = None,
    ):
        query = """
        INSERT INTO user_feedback (feedback_id, user_id, feedback_type, description, screenshot)
        VALUES (%s, %s, %s, %s, %s)
        """
        try:
            self.cursor.execute(
                query,
                (
                    feedback_id,
                    user_id,
                    feedback_type,
                    description,
                    screenshot,
                ),
            )
        except DatabaseError as e:
            self.conn.rollback()
            raise e

    def insert_domain_info(
        self, user_id: str, domain_id: str, domain_name: str, domain_type: int
    ):
        query_insert_domain_info = """
        INSERT INTO domain_info (user_id, domain_id, domain_name, domain_type)
        VALUES (%s, %s, %s, %s)
        """
        try:
            self.cursor.execute(
                query_insert_domain_info,
                (
                    user_id,
                    domain_id,
                    domain_name,
                    domain_type,
                ),
            )
        except DatabaseError as e:
            self.conn.rollback()
            raise e

    def create_domain(
        self, user_id: str, domain_name: str, domain_id: str, domain_type: int
    ):
        query_count_domains = """
        SELECT COUNT(*)
        FROM domain_info
        WHERE user_id = %s
        """

        try:
            self.cursor.execute(query_count_domains, (user_id,))
            domain_count = self.cursor.fetchone()[0]

            if domain_count >= 10:
                return None

            query_insert = """
            INSERT INTO domain_info (user_id, domain_id, domain_name, domain_type)
            VALUES (%s, %s, %s, %s)
            RETURNING domain_id
            """

            self.cursor.execute(
                query_insert, (user_id, domain_id, domain_name, domain_type)
            )
            created_domain_id = self.cursor.fetchone()[0]

            return 1 if created_domain_id else None

        except DatabaseError as e:
            self.conn.rollback()
            raise e

    def insert_file_batches(
        self, file_info_batch: list, file_content_batch: list
    ) -> bool:
        """Process both file info and content in a single transaction."""
        try:
            self._insert_file_info_batch(file_info_batch)
            self._insert_file_content_batch(file_content_batch)

            return True
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error in batch processing: {str(e)}")
            return False

    def _insert_file_info_batch(self, file_info_batch: list):
        """Internal method for file info insertion."""
        query = """
        INSERT INTO file_info (user_id, file_id, domain_id, file_name, file_modified_date)
        VALUES %s
        """
        try:
            extras.execute_values(self.cursor, query, file_info_batch)
            logger.info(
                f"Successfully inserted {len(file_info_batch)} file info records"
            )

        except Exception as e:
            logger.error(f"Error while inserting file info: {str(e)}")
            raise

    def _insert_file_content_batch(self, file_content_batch: list):
        """Internal method for file content insertion."""
        query = """
        INSERT INTO file_content (file_id, sentence, page_number, is_header, is_table, embedding)
        VALUES %s
        """
        try:
            extras.execute_values(self.cursor, query, file_content_batch)
            logger.info(
                f"Successfully inserted {len(file_content_batch)} content rows "
            )

        except Exception as e:
            logger.error(f"Error while inserting file content: {str(e)}")
            raise

    def insert_session_info(self, user_id: str, session_id: str):
        query = """
        INSERT INTO session_info (user_id, session_id, created_at)
        VALUES (%s, %s, NOW())
        """
        try:
            self.cursor.execute(query, (user_id, session_id))
        except Exception as e:
            self.conn.rollback()
            raise e

    def update_session_info(self, user_id: str, session_id: str):
        query = """
        UPDATE session_info 
        SET question_count = question_count + 1
        WHERE user_id = %s AND session_id = %s
        RETURNING question_count
        """
        try:
            self.cursor.execute(query, (user_id, session_id))
            question_count = self.cursor.fetchone()[0]
            return question_count
        except Exception as e:
            self.conn.rollback()
            raise e

    def insert_user_rating(
        self, rating_id: str, user_id: str, rating: int, user_note: str
    ):
        query = """
        INSERT INTO user_rating (rating_id, user_id, rating, user_note)
        VALUES (%s, %s, %s, %s)
        """
        try:
            self.cursor.execute(query, (rating_id, user_id, rating, user_note))
        except Exception as e:
            self.conn.rollback()
            raise e

    def clear_file_info(self, user_id: str, file_ids: list):
        query = """
        DELETE FROM file_info
        WHERE user_id = %s AND file_id IN %s
        """
        try:
            self.cursor.execute(
                query,
                (
                    user_id,
                    tuple(
                        file_ids,
                    ),
                ),
            )
            return 1
        except DatabaseError as e:
            self.conn.rollback()
            raise e

    def clear_file_content(self, file_id: list):
        clear_content_query = """
        DELETE FROM file_content
        WHERE file_id = %s
        """
        clear_file_info_query = """
        DELETE FROM file_info
        WHERE file_id = %s
        """
        try:
            self.cursor.execute(
                clear_content_query,
                (file_id,),
            )

            self.cursor.execute(
                clear_file_info_query,
                (file_id,),
            )

            rows_affected = self.cursor.rowcount

            return 1 if rows_affected else 0

        except DatabaseError as e:
            self.conn.rollback()
            raise e


if __name__ == "__main__":
    with Database() as db:
        db.reset_database()
        db.initialize_tables()
