from fastapi import FastAPI, HTTPException 
from db import get_db_connection 
import hashlib, re
import secrets
from datetime import datetime
from utils import generar_transaccion
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
    
    # Validar que sea un hash MD5 (32 caracteres hexadecimales)
    if not re.fullmatch(r"[a-fA-F0-9]{32}", data.contrasena):
        raise HTTPException(status_code=400, detail="Formato de hash inválido")
        
    cursor.execute("""
        SELECT u.nombre, u.contraseña, r.rol 
        FROM usuarios u
        JOIN rol r ON u.rol_id = r.id
        WHERE u.nombre = %s 
        AND u.contraseña = %s 
    """, (data.nombre, data.contrasena))

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

@app.post("/usuario")
def crear_usuario(usuario: UsuarioCreate):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

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

    if rol['rol'].lower() == "administrador":
        cursor.close()
        conn.close()
        raise HTTPException(status_code=403, detail="No es posible asignar el rol de administrador.")

    # 3. Validar que sea un hash MD5 (32 caracteres hexadecimales)
    if not re.fullmatch(r"[a-fA-F0-9]{32}", usuario.contrasena):
        raise HTTPException(status_code=400, detail="Formato de hash inválido")

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



        # Insertar venta
        cursor.execute("INSERT INTO ventas (transaccion, fecha, hora, total) VALUES (%s, %s, %s, %s)", 
                    (transaccion,venta.fecha, venta.hora, venta.total))
        venta_id = cursor.lastrowid

        # Insertar items y actualizar stock
        for item in venta.items:
            cursor.execute(
                "INSERT INTO detalle_ventas (venta_id, producto_id, cantidad, precio, precio_con_iva, subtotal) VALUES (%s, %s, %s, %s, %s, %s)",
                (venta_id, item.id, item.cantidad, item.precio, item.precio_con_iva, item.subtotal)
            )
            cursor.execute("""
                            UPDATE datos_productos 
                            SET cantidad = cantidad - %s
                            WHERE producto_id=%s
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