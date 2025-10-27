from pydantic import BaseModel

# -------- Vinculación y Login --------
class VinculacionRequest(BaseModel):
    correo: str
    codigo: int

class LoginRequest(BaseModel):
    nombre: str
    contrasena: str

# -------- Usuarios --------
class UsuarioNombre(BaseModel):
    nombre: str

class UsuarioContrasena(BaseModel):
    contrasena: str

# -------- Productos --------
class ProductoNuevo(BaseModel):
    nombre: str
    categoria_id: int
    precio: int
    cantidad: int

class ProductoUpdate(BaseModel):   # Para stock y precio
    precio: int | None = None
    cantidad: int | None = None




# -------- Categorías --------
class CategoriaCreate(BaseModel):
    categoria: str

class CategoriaUpdate(BaseModel):
    categoria_id: int

# -------- Subcategorías --------
class SubCategoriaCreate(BaseModel):
    nombre: str




