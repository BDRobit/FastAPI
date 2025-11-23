from fastapi import FastAPI, status, HTTPException, Query, Depends 
from db import get_db_connection, get_db_connection_cliente, get_db_connection_principal  
import hashlib, re
import secrets
from datetime import datetime, timedelta
from utils import generar_transaccion
from typing import Optional
from models import (
    VinculacionRequest,
    LoginRequest,
    CategoriaCreate,
    CategoriaUpdate,
    SubCategoriaCreate,
    UsuarioNombre,
    UsuarioContrasena,
    ProductoNuevo,
    ProductoUpdate,
    VentaItem,
    VentaCreate,
    UsuarioCreate
)
from auth import require_admin, require_bodega, require_cajero, requiere_acceso
from jose import jwt
from auth import ALGORITHM, SECRET_KEY
from fastapi.security import HTTPBearer
from fastapi import Security

auth_scheme = HTTPBearer()


# GET para la configuración de páginas web (filtros, ordenación, búsquedas, etc.)
# POST para la transferencia de información y datos

app = FastAPI(
    title="mi api",
    descripcion ="fast api",
    version="0.1.0"
)


# ---  Verificación para APP ---
@app.get("/")
def root():
    return {
        "message": "API funcionando correctamente",
        "status":"Ok"
        }

def get_client_db_name(correo: str, codigo: str) -> Optional[str]:
    """Obtiene el nombre de la BD del cliente verificando correo y código."""
    conn_principal = get_db_connection_principal()
    cursor = conn_principal.cursor(dictionary=True)
    db_name = None
    try:
        cursor.execute("""
            SELECT bd.base_datos
            FROM cliente c
            JOIN base_datos bd ON c.id = bd.cliente_id
            WHERE c.correo = %s AND c.codigo = %s
        """, (correo, codigo))
        
        result = cursor.fetchone()
        if result:
            db_name = result["base_datos"]
    finally:
        cursor.close()
        conn_principal.close()
        
    return db_name

#---  vincular  ---


@app.post("/vincular")
def vincular_cliente(data: VinculacionRequest):
    # 1. PASO DE BÚSQUEDA: Obtener el nombre de la BD.
    db_name = get_client_db_name(data.correo, data.codigo)

    if not db_name:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Correo o código incorrectos, o cliente no encontrado."
        )
        
    # 2. PASO DE CONEXIÓN: Conectarse a la BD dinámica.
    conn_cliente = get_db_connection_cliente(db_name)
    
    if not conn_cliente:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Error al conectar con la base de datos del cliente."
        )

    try:
        cursor_cliente = conn_cliente.cursor(dictionary=True)
        codigo_vinculacion = secrets.token_hex(8)

        cursor_cliente.execute(
            "INSERT INTO codigo (codigo_vinculacion, fecha_vinculacion) VALUES (%s, %s)",
            (codigo_vinculacion, data.fecha)
        )
        conn_cliente.commit()
        
        payload = {
            "sub": data.correo,
            "codigo_vinculacion": codigo_vinculacion,
            "cliente_db": db_name,
        }

        token_vinculacion = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        return {
            "token_vinculacion": token_vinculacion,
        }
    finally:
        conn_cliente.close()

# --- Login con rol ---
@app.post("/login")
def login(data: LoginRequest, payload: dict = Depends(requiere_acceso)):

    db_name = payload.get("cliente_db")
    # print("este ",db_name)

    conn = get_db_connection_cliente(db_name)
    cursor = conn.cursor(dictionary=True)
    
    # Validar que sea un hash MD5 (32 caracteres hexadecimales)
    if not re.fullmatch(r"[a-fA-F0-9]{32}", data.contrasena):
        raise HTTPException(status_code=400, detail="Formato de hash inválido")
        
    cursor.execute("""
        SELECT u.id, u.nombre, u.contraseña, r.rol, r.id 
        FROM usuarios u
        JOIN rol r ON u.rol_id = r.id
        WHERE u.nombre = %s 
        AND u.contraseña = %s 
    """, (data.nombre, data.contrasena))

    usuario = cursor.fetchone()
    conn.close()

    if usuario:
        # Crear el payload del token
        payload = {
            "sub": payload.get("sub"),
            "codigo_vinculacion": payload.get("codigo_vinculacion"),
            "cliente_db": payload.get("cliente_db"),
            "r.id": str(usuario["id"]),
            "nombre": usuario["nombre"],
            "rol": usuario["rol"]
        }

        # Generar el token
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        print(token)
        token2 = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(token2)
        return {
            "status": "ok",
            "rol": usuario["rol"],
            "token": token,
            "acceso": f"Panel de {usuario['rol']}",
            "se borrara": f"datos enviados,{payload}"
        }

    else:
        raise HTTPException(status_code=401, detail="Credenciales inválidas o vinculación no válida")

    """
    if usuario:
        return {
            "status": "ok",
            "rol": usuario["rol"],
            "acceso": f"Panel de {usuario['rol']}"
        }
    else:
        raise HTTPException(status_code=401, detail="Credenciales inválidas o vinculación no válida")
    """

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

    cursor.execute("""
                    SELECT u.id, u.nombre, r.rol 
                    FROM usuarios u
                    JOIN rol r
                    WHERE u.rol_id = r.id
                    order by u.id asc
                    """)
    usuarios = cursor.fetchall()

    cursor.close()
    conn.close()
    return {"usuario": usuarios}

@app.post("/usuario")
def crear_usuario(usuario: UsuarioCreate):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # --------------------
    # Verificacion de solo letras
    if not re.fullmatch(r"^[a-zA-Z]+$", usuario.nombre):
        raise HTTPException(
            status_code=400, 
            detail="Solo debe contener letras empezando con mayuscula y sin espacios."
        )

    # Comparacion de enviado con esperado
    nombre_enviado = usuario.nombre.strip()
    nombre_esperado = nombre_enviado.capitalize()
    
    if nombre_enviado != nombre_esperado:
        raise HTTPException(
            status_code=400, 
            detail=f"El nombre debe tener la primera letra en mayúscula y el resto en minúscula. Formato esperado: '{nombre_esperado}'."
        )
    # negacion a crear un administrador
    if usuario.rol_id == 1:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=403, detail="No es posible asignar el rol de administrador.")

    # Validar que sea un hash MD5 (32 caracteres hexadecimales)
    if not re.fullmatch(r"[a-fA-F0-9]{32}", usuario.contrasena):
        raise HTTPException(status_code=400, detail="Formato de hash inválido")

    # 1. Verificar si el nombre ya existe
    cursor.execute("SELECT id FROM usuarios WHERE nombre = %s", (usuario.nombre,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail="El nombre de usuario ya está en uso.")

    # 2. Validar rol
    cursor.execute("SELECT rol FROM rol WHERE id = %s", (usuario.rol_id,))
    rol = cursor.fetchone()
    if not rol:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail="El rol especificado no existe.")

    # 4. Insertar el nuevo usuario
    cursor.execute(
        "INSERT INTO usuarios (cliente_id, nombre, contraseña, rol_id, fecha_creacion) VALUES (%s, %s, %s, %s,%s)",
        (1, usuario.nombre, usuario.contrasena, usuario.rol_id, usuario.fecha)
    )
    conn.commit()

    cursor.close()
    conn.close()

    return {"message": "Usuario creado exitosamente."}

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

#############################################################
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








#########################################################
#-- Producto -- 

@app.get("/muestra_productos")
def muestra_productos():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)  # obligatorio para que devuelva dict
    
    cursor.execute("""
		SELECT p.id, p.nombre, c.categoria, d.valor, d.cantidad   
        FROM productos p
        JOIN categorias c ON p.categoria_id = c.id
		JOIN datos_productos d ON p.id = d.producto_id;
    """)
    
    productos = cursor.fetchall()
    conn.close()
    
    if not productos:
        raise HTTPException(status_code=404, detail="No hay productos registrados")
    
    return [
        {
            "id": prod["id"],
            "nombre": prod["nombre"],
            "categoria": prod["categoria"],
            "precio": prod["valor"],
            "stock": prod["cantidad"]
        }
        for prod in productos
    ]



@app.put("/producto/{id}/")
def actualizar_producto(id: int, datos: ProductoUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Construimos query dinámicamente según los campos que vienen
    campos = []
    valores = []
    
    if datos.precio is not None:
        campos.append("valor = %s")
        valores.append(datos.precio)
    if datos.cantidad is not None:
        campos.append("cantidad = %s")
        valores.append(datos.cantidad)
    
    if not campos:
        raise HTTPException(status_code=400, detail="No se proporcionaron datos para actualizar")
    
    valores.append(id)
    query = f"UPDATE datos_productos SET {', '.join(campos)} WHERE producto_id = %s"
    cursor.execute(query, valores)
    conn.commit()
    
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    conn.close()
    return {"mensaje": "Producto actualizado correctamente"}


@app.post("/producto/")
def agregar_producto(prod: ProductoNuevo):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Verificar que la categoría exista
    cursor.execute("SELECT id FROM categorias WHERE id = %s", (prod.categoria_id,))
    if cursor.fetchone() is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    # Insertar en productos
    cursor.execute(
        "INSERT INTO productos (nombre, categoria_id) VALUES (%s, %s)",
        (prod.nombre, prod.categoria_id)
    )
    producto_id = cursor.lastrowid  # obtenemos el id recién insertado
    
    # Insertar en datos_productos
    cursor.execute(
        "INSERT INTO datos_productos (producto_id, cantidad, valor, fecha_creacion) VALUES (%s, %s, %s, %s)",
        (producto_id, prod.cantidad, prod.precio, datetime.now())
    )
    
    conn.commit()
    conn.close()
    
    return {"mensaje": "Producto agregado correctamente", "producto_id": producto_id}

@app.put("/producto/{id}/categoria")
def actualizar_categoria(id: int, data: CategoriaUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Verificar que el producto exista
    cursor.execute("SELECT id FROM productos WHERE id = %s", (id,))
    if cursor.fetchone() is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Verificar que la categoría exista
    cursor.execute("SELECT id FROM categorias WHERE id = %s", (data.categoria_id,))
    if cursor.fetchone() is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    # Actualizar categoría
    cursor.execute(
        "UPDATE productos SET categoria_id = %s WHERE id = %s",
        (data.categoria_id, id)
    )
    conn.commit()
    conn.close()
    
    return {"mensaje": "Categoría del producto actualizada correctamente"}

@app.delete("/producto/{id}")
def eliminar_producto(id: int):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Verificar si el producto existe
    cursor.execute("SELECT id FROM productos WHERE id = %s", (id,))
    if cursor.fetchone() is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # Verificar cantidad disponible
    cursor.execute("SELECT cantidad FROM datos_productos WHERE producto_id = %s", (id,))
    datos = cursor.fetchone()
    if not datos:
        conn.close()
        raise HTTPException(status_code=404, detail="No hay datos asociados al producto")

    if datos["cantidad"] > 0:
        conn.close()
        raise HTTPException(status_code=400, detail="No se puede eliminar un producto con stock disponible. Primero deje cantidad en 0.")

    # Eliminar de datos_productos
    cursor.execute("DELETE FROM datos_productos WHERE producto_id = %s", (id,))

    # Luego eliminar el producto
    cursor.execute("DELETE FROM productos WHERE id = %s", (id,))
    conn.commit()
    conn.close()

    return {"mensaje": "Producto eliminado correctamente"}



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
def crear_categoria(categoria: CategoriaCreate, payload: dict = Depends(require_cajero)):
    db_name = payload.get("cliente_db")

    conn = get_db_connection_cliente(db_name)
    cursor = conn.cursor()

    try:
        if not re.match(r'^[A-ZÁÉÍÓÚÑ][a-záéíóúñ ]+$', categoria.categoria):
            raise HTTPException(
                status_code=400,
                detail="Solo letras <Electrodomésticos> Primera mayúscula continuar en minúsculas."
            )
        # ⚠️ Verificar si ya existe una categoría con ese nombre
        cursor.execute("SELECT id FROM categorias WHERE categoria = %s", (categoria.categoria,))
        existente = cursor.fetchone()
        if existente:
            raise HTTPException(
                status_code=400,
                detail=f"La categoría '{categoria.categoria}' ya existe."
            )
        # Insertar nueva categoría
        cursor.execute(
            "INSERT INTO categorias (categoria) VALUES (%s)",
            (categoria.categoria,)
        )
        conn.commit()

        # Obtener el id autogenerado
        nueva_id = cursor.lastrowid
        return {"mensaje": "Categoría creada correctamente", "id": nueva_id, "categoria": categoria.categoria}

    finally:
        cursor.close()
        conn.close()

@app.delete("/categorias/{id}")
def eliminar_categoria(id: int):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Verificar si la categoría existe
    cursor.execute("SELECT id FROM categorias WHERE id = %s", (id,))
    if cursor.fetchone() is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    # Verificar que no esté en uso por productos
    cursor.execute("SELECT COUNT(*) AS total FROM productos WHERE categoria_id = %s", (id,))
    resultado = cursor.fetchone()
    if resultado["total"] > 0:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar la categoría porque está siendo utilizada por productos."
        )

    # Si no está en uso, eliminar
    cursor.execute("DELETE FROM categorias WHERE id = %s", (id,))
    conn.commit()
    conn.close()

    return {"mensaje": "Categoría eliminada correctamente"}


## sub categorias

@app.get("/subcategorias")
def listar_subcategorias(
    cliente_db: str,
    codigo: str,
    payload: dict = Depends(require_admin)
    ):
    print("Usuario logueado:", payload)
    conn_client = get_db_connection_cliente(cliente_db)
    cursor = conn_client.cursor(dictionary=True)

    cursor.execute("SELECT id, nombre FROM sub_categorias")
    subcategorias = cursor.fetchall()

    cursor.close()
    conn_client.close()
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

    nueva_id = cursor.lastrowid    # Obtener el id autogenerado

    cursor.close()
    conn.close()

    return {"mensaje": "Subcategoría creada correctamente", "id": nueva_id, "categoria": categorias.nombre}




@app.post("/ventas")
def procesar_venta(venta: VentaCreate):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:

        transaccion = generar_transaccion()

        # Verificar cada producto
        total_calculado = 0
        for item in venta.items:

            cursor.execute("""
                SELECT p.id, p.nombre, d.valor as precio, d.cantidad as stock   
                FROM productos p
                JOIN datos_productos d ON p.id = d.producto_id
                Where p.id=%s;
                """, (item.id,))

            producto_bd = cursor.fetchone()
            if not producto_bd:
                conn.close()
                raise HTTPException(status_code=404, detail=f"Producto {item.id} no encontrado")
            
            # Validar precio
            if producto_bd['precio'] != item.precio:
                conn.close()
                raise HTTPException(status_code=400, detail=f"Precio del producto {item.id} no coincide")
            
            # Validar stock
            if producto_bd['stock'] < item.cantidad:
                conn.close()
                raise HTTPException(status_code=400, detail=f"No hay stock suficiente para el producto {item.id}")
            
            total_calculado += item.subtotal

            IVA = 0.19

            for item in venta.items:
                # Calcular precio con IVA según el precio unitario
                precio_con_iva_calculado = round(item.precio * (1 + IVA))

                if precio_con_iva_calculado != item.precio_con_iva:
                    raise HTTPException(
                        status_code=400,
                        detail=f"El precio con IVA del producto ID {item.id} no es válido. "
                            f"Debe ser {precio_con_iva_calculado} y llegó {item.precio_con_iva}"
                    )

                # Calcular subtotal según la cantidad
                subtotal_calculado = precio_con_iva_calculado * item.cantidad
                if subtotal_calculado != item.subtotal:
                    raise HTTPException(
                        status_code=400,
                        detail=f"El subtotal del producto ID {item.id} es incorrecto. "
                            f"Debe ser {subtotal_calculado} y llegó {item.subtotal}"
                    )

        # Validar total
        if total_calculado != venta.total:
            conn.close()
            raise HTTPException(status_code=400, detail="El total no coincide con la suma de subtotales")

        #####  Aca si algo falla deberia de hacer rollback

        #print("venta" ,venta)
        

        # Insertar venta
        cursor.execute("INSERT INTO ventas (transaccion, fecha, hora, total) VALUES (%s, %s, %s, %s)", 
                    (transaccion,venta.fecha, venta.hora, venta.total))
        venta_id = cursor.lastrowid

        print("detalle" ,venta_id, item.id, item.cantidad, item.precio, item.precio_con_iva, item.subtotal )

        # Insertar items y actualizar stock
        for item in venta.items:
            cursor.execute(
                "INSERT INTO detalle_ventas (venta_id, producto_id, cantidad, precio, precio_con_iva, subtotal) VALUES (%s, %s, %s, %s, %s, %s)",
                (venta_id, item.id, item.cantidad, item.precio, item.precio_con_iva, item.subtotal)
            )
            cursor.execute("""
                            UPDATE datos_productos
                            SET cantidad = cantidad - %s
                            WHERE producto_id = %s;
                            """,
                (item.cantidad, item.id)
            )

        conn.commit()
        conn.close()

        # Retornar mensaje
        return {"mensaje": "Venta realizada con éxito", "numero_transaccion": transaccion}

    except Exception as e:
        conn.rollback()  # <<< IMPORTANTE: Revertimos todo si algo falla
        raise HTTPException(status_code=500, detail=f"Error en la venta: {str(e)}")

    finally:
        conn.close()

@app.get("/ListadoVentas")
def listar_ventas(
    start_date: Optional[str] = Query(None, description="Fecha de inicio en formato YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Fecha de fin en formato YYYY-MM-DD")
):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Construimos la consulta base
    query = """
        SELECT 
            v.id AS venta_id,
            v.transaccion,
            v.fecha,
            v.hora,
            v.total AS total_venta,
            u.nombre AS vendedor,
            p.nombre AS producto,
            dv.cantidad,
            dv.precio,
            dv.precio_con_iva,
            dv.subtotal
        FROM ventas v
        LEFT JOIN usuarios u 
            ON v.id_usuario = u.id
        LEFT JOIN detalle_ventas dv 
            ON dv.venta_id = v.id
        LEFT JOIN productos p 
            ON dv.producto_id = p.id
    """

    # Filtro opcional por fechas
    params = []
    if start_date and end_date:
        query += " WHERE v.fecha BETWEEN %s AND %s"
        params.extend([start_date, end_date])
    elif start_date:
        query += " WHERE v.fecha >= %s"
        params.append(start_date)
    elif end_date:
        query += " WHERE v.fecha <= %s"
        params.append(end_date)

    query += " ORDER BY v.fecha DESC, v.hora DESC, v.id, dv.id;"

    cursor.execute(query, tuple(params))
    ventas = cursor.fetchall()

    cursor.close()
    conn.close()
    return {"Ventas": ventas}