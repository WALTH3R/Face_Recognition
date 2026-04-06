import mysql.connector
from mysql.connector import Error
import cv2

class DatabaseManager:
    def __init__(self):
        self.host = "localhost"
        self.port = 3307
        self.user = "root"
        self.password = ""
        self.database = "Face_Rec"

    def connect(self):
        """Establish a connection to the MySQL database."""
        try:
            connection = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database
            )
            return connection
        except Error as e:
            print(f"Error connecting to MySQL Database: {e}")
            return None

    def insert_student(self, name):
        """Insert a new student and return their student_id."""
        conn = self.connect()
        if not conn: return None
        
        try:
            cursor = conn.cursor()
            # Insert or ignore (if student already exists just fetch the ID)
            query = "INSERT IGNORE INTO students (student_name) VALUES (%s)"
            cursor.execute(query, (name,))
            conn.commit()

            cursor.execute("SELECT student_id FROM students WHERE student_name = %s", (name,))
            student_id = cursor.fetchone()[0]
            return student_id
        except Error as e:
            print(f"Failed inserting student: {e}")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()

    def insert_face_image(self, student_id, cv2_image):
        """Convert a cv2 image numpy array into binary data and store it in the database."""
        conn = self.connect()
        if not conn: return
        
        try:
            # Convert NumPy Array into JPG bytes
            success, buffer = cv2.imencode('.jpg', cv2_image)
            if not success:
                print("Failed to convert image to bytes.")
                return
            
            image_bytes = buffer.tobytes()

            cursor = conn.cursor()
            query = "INSERT INTO dataset_images (student_id, image_data) VALUES (%s, %s)"
            cursor.execute(query, (student_id, image_bytes))
            conn.commit()
        except Error as e:
            print(f"Failed inserting image: {e}")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
                
    def load_student_images(self, student_name):
        """Fetch all images for a specific student for encoding."""
        conn = self.connect()
        if not conn: return []
        
        images_data = []
        try:
            cursor = conn.cursor()
            query = '''
            SELECT d.image_data FROM dataset_images d 
            JOIN students s ON d.student_id = s.student_id 
            WHERE s.student_name = %s
            '''
            cursor.execute(query, (student_name,))
            results = cursor.fetchall()
            
            for row in results:
                # row[0] contains the binary image data (LONGBLOB)
                images_data.append(row[0])
                
            return images_data
        except Error as e:
            print(f"Failed fetching images: {e}")
            return []
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()

    def get_all_students(self):
        """Fetch a list of all student names in the database."""
        conn = self.connect()
        if not conn: return []
        
        students = []
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT student_name FROM students")
            results = cursor.fetchall()
            for row in results:
                students.append(row[0])
            return students
        except Error as e:
            print(f"Failed fetching students: {e}")
            return []
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
