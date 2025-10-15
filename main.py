from fastapi import FastAPI, HTTPException 
from pydantic import BaseModel
import mysql.connector
import hashlib
import secrets


# GET para la configuración de páginas web (filtros, ordenación, búsquedas, etc.)
# POST para la transferencia de información y datos

app = FastAPI(
    title="mi api",
    descripcion ="fast api",
    version="0.1.0"
)

# Modelo para recibir datos del front
class VinculacionRequest(BaseModel):
    correo: str
    codigo: int

class LoginRequest(BaseModel):
    rol: str
    contraseña: str 
    codigo_vinculacion: str

class ProductoUpdate(BaseModel):
    nombre: str
    descripcion: str

class CategoriaCreate(BaseModel):
    categoria: str

class SubCategoriaCreate(BaseModel):
    nombre: str

# Modelo para actualizar solo nombre
class UsuarioNombre(BaseModel):
    nombre: str

# Modelo para actualizar solo contraseña
class UsuarioContrasena(BaseModel):
    contrasena: str

# Conexión a MySQL
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="base0001a"
    )

# --- Vinculacion y logueo  ---

@app.post("/vincular")
def vincular(data: VinculacionRequest):

    print("datos",data)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT correo , codigo FROM cliente WHERE correo=%s AND codigo=%s", 
                    (data.correo, data.codigo))
    usuario = cursor.fetchone()

    print("vincular",usuario)

    if usuario:
        # Generar código de vinculación único
        codigo_vinculacion = secrets.token_hex(8)
        cursor.execute("insert into codigo (codigo_vinculacion) values (%s)", 
                        (codigo_vinculacion,))
        conn.commit()
        conn.close()
        return {"status": "ok", "codigo_vinculacion": codigo_vinculacion}
    else:
        conn.close()
        raise HTTPException(status_code=401, detail="Correo o código inválido")

# --- Login con rol ---
@app.post("/login")
def login(data: LoginRequest):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ⚠️ Aquí podrías usar hash con bcrypt en lugar de MD5
    hashed_pass = hashlib.md5(data.contraseña.encode()).hexdigest()

    cursor.execute("""
        SELECT r.id, r.rol, u.contraseña
        FROM usuarios u
        JOIN rol r ON u.rol_id = r.id
        WHERE r.rol = %s 
        AND u.contraseña = %s 
        AND EXISTS (
            SELECT 1 FROM codigo WHERE codigo_vinculacion = %s
        )
    """, (data.rol, hashed_pass, data.codigo_vinculacion))

    usuario = cursor.fetchone()
    conn.close()

    if usuario:
        return {
            "status": "ok",
            "rol": usuario["rol"],
            "acceso": f"Panel de {usuario['rol']}"
        }
    else:
        raise HTTPException(status_code=401, detail="Credenciales inválidas o vinculación no válida")




# --- Bodega ver producto ---

@app.get("/producto/{id}")
def ver_producto(id:int):
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True) #no es opcional
    #cursor.execute( "SELECT * FROM productos WHERE id = %s", (id,))

    cursor.execute("""
        SELECT p.id, p.nombre, p.descripcion, c.categoria , s.nombre AS subcategorias
        FROM productos p
        JOIN categorias c ON p.categoria_id = c.id
        JOIN sub_categorias s ON p.categoria_id = s.id
        WHERE p.id = %s
    """, (id,))

    producto = cursor.fetchone()
    conn.close()
    print("este", producto)
    if producto is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    print("salida", producto)

    return {"id": producto["id"],
            "nombre": producto["nombre"],
            "descripcion": producto["descripcion"],
            "categoria": producto["categoria"],
            "subcategorias": producto["subcategorias"]
            }

@app.get("/productos")
def listar_productos():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)  # obligatorio para que devuelva dict
    
    cursor.execute("""
		SELECT p.id, p.nombre, p.descripcion, c.categoria , s.nombre AS subcategorias
        FROM productos p
        JOIN categorias c ON p.categoria_id = c.id
		JOIN sub_categorias s ON p.categoria_id = s.id
    """)
    
    productos = cursor.fetchall()
    conn.close()
    
    if not productos:
        raise HTTPException(status_code=404, detail="No hay productos registrados")
    
    return [
        {
            "id": prod["id"],
            "nombre": prod["nombre"],
            "descripcion": prod["descripcion"],
            "categoria": prod["categoria"],
            "subcategorias": prod["subcategorias"]
        }
        for prod in productos
    ]

@app.put("/producto/{id}")
def update_producto(id: int, producto: ProductoUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Verificar si el producto existe
    cursor.execute("SELECT id FROM productos WHERE id = %s", (id,))
    existente = cursor.fetchone()
    if not existente:
        conn.close()
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # Actualizar producto
    cursor.execute("""
        UPDATE productos
        SET nombre = %s, descripcion = %s
        WHERE id = %s
    """, (producto.nombre, producto.descripcion, id))
    conn.commit()
    conn.close()

    return {"mensaje": "Producto actualizado correctamente", "id": id}

############################################################
## Categorias

@app.get("/categorias")
def listar_categorias():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, categoria FROM categorias")
    categorias = cursor.fetchall()

    cursor.close()
    conn.close()
    return {"categorias": categorias}

@app.post("/categorias")
def crear_categoria(categoria: CategoriaCreate):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Insertar nueva categoría
    cursor.execute(
        "INSERT INTO categorias (categoria) VALUES (%s)",
        (categoria.categoria,)
    )
    conn.commit()

    # Obtener el id autogenerado
    nueva_id = cursor.lastrowid

    cursor.close()
    conn.close()
    return {"mensaje": "Categoría creada correctamente", "id": nueva_id, "categoria": categoria.categoria}

## sub categorias

@app.get("/subcategorias")
def listar_subcategorias():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, nombre FROM sub_categorias")
    subcategorias = cursor.fetchall()

    cursor.close()
    conn.close()
    return {"subcategorias": subcategorias}

@app.post("/subcategorias")
def crear_subcategoria(categorias: SubCategoriaCreate):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Insertar nueva categoría
    cursor.execute(
        "INSERT INTO sub_categorias (nombre) VALUES (%s)",
        (categorias.nombre,)
    )
    conn.commit()

    # Obtener el id autogenerado
    nueva_id = cursor.lastrowid

    cursor.close()
    conn.close()

    return {"mensaje": "Subcategoría creada correctamente", "id": nueva_id, "categoria": categorias.nombre}

#####################################################
#  Usuarios

@app.get("/rol")
def listar_roles():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, rol FROM rol")
    rol = cursor.fetchall()

    cursor.close()
    conn.close()
    return {"rol": rol}





@app.get("/usuarios")
def listar_usuarios():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, nombre FROM usuarios")
    usuarios = cursor.fetchall()

    cursor.close()
    conn.close()
    return {"usuario": usuarios}


@app.put("/usuarios/{id}/nombre")
def actualizar_nombre_usuario(id: int, usuario: UsuarioNombre):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM usuarios WHERE id = %s", (id,))
    existente = cursor.fetchone()
    if not existente:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    cursor.execute("""
        UPDATE usuarios
        SET nombre = %s
        WHERE id = %s
    """, (usuario.nombre, id))
    conn.commit()
    cursor.close()
    conn.close()
    return {"mensaje": "Nombre de usuario actualizado correctamente", "id": id}


# ✅ Actualizar solo la contraseña (MD5)
@app.put("/usuarios/{id}/contrasena")
def actualizar_contrasena_usuario(id: int, usuario: UsuarioContrasena):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM usuarios WHERE id = %s", (id,))
    existente = cursor.fetchone()
    if not existente:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    hashed_pass = hashlib.md5(usuario.contrasena.encode()).hexdigest()

    cursor.execute("""
        UPDATE usuarios
        SET contraseña = %s
        WHERE id = %s
    """, (hashed_pass, id))
    conn.commit()

    cursor.close()
    conn.close()

    return {"mensaje": "Contraseña actualizada correctamente", "id": id}









