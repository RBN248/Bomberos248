import os
import sqlite3
import csv
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'bomberos_m_acosta_2025'

base_dir = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(base_dir, 'instance')
if not os.path.exists(instance_path): os.makedirs(instance_path)

db_path = os.path.join(instance_path, 'bomberos_ma.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ==========================================
# --- MODELOS (ESTRUCTURA DE BASE DE DATOS) ---
# ==========================================



class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password_hash = db.Column(db.String(128))
    rol = db.Column(db.String(50), default="Cuartelero")

class Bombero(db.Model):
    __tablename__ = 'bomberos'
    numero = db.Column(db.String(20), primary_key=True)
    apellido = db.Column(db.String(100))
    nombre = db.Column(db.String(100))

class Movil(db.Model):
    __tablename__ = 'moviles'
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True)
    descripcion = db.Column(db.String(100))
    estado = db.Column(db.String(20), default="Activo") # Para dar de baja sin borrar

class ParteServicio(db.Model):
    __tablename__ = 'parte_servicio'
    id = db.Column(db.Integer, primary_key=True)
    nro_acta = db.Column(db.String(20))
    tipo_siniestro = db.Column(db.String(100))
    ubicacion = db.Column(db.String(200))
    hora_alarma = db.Column(db.DateTime, default=datetime.now)
    # CAMPOS DEL DENUNCIANTE
    denunciante_nombre = db.Column(db.String(100)) 
    denunciante_tel = db.Column(db.String(50))
    hora_denuncia = db.Column(db.DateTime)
    # CAMPOS TÉCNICOS (Dejalos así una sola vez)
    panorama = db.Column(db.Text)
    disposiciones = db.Column(db.Text)
    pol_movil = db.Column(db.String(50))
    pol_cargo = db.Column(db.String(100))
    pol_obs = db.Column(db.Text)
    amb_movil = db.Column(db.String(50))
    amb_cargo = db.Column(db.String(100))
    amb_obs = db.Column(db.Text)
    dc_movil = db.Column(db.String(50))
    dc_cargo = db.Column(db.String(100))
    dc_obs = db.Column(db.Text)
    tareas_realizadas = db.Column(db.Text)
    estado = db.Column(db.String(20), default="En curso")

class DotacionMovil(db.Model):
    __tablename__ = 'dotaciones_moviles'
    id = db.Column(db.Integer, primary_key=True)
    parte_id = db.Column(db.Integer, db.ForeignKey('parte_servicio.id'))
    movil_id = db.Column(db.Integer, db.ForeignKey('moviles.id'))
    bombero_numero = db.Column(db.String(20), db.ForeignKey('bomberos.numero'))
    rol_en_unidad = db.Column(db.String(50))
    
    # CAMPOS NUEVOS (Sin cambiar los anteriores)
    hora_salida = db.Column(db.DateTime)
    hora_llegada = db.Column(db.DateTime)
    hora_regreso = db.Column(db.DateTime)

    movil = db.relationship('Movil')
    bombero = db.relationship('Bombero')

class AsistenciaCuartel(db.Model):
    __tablename__ = 'asistencias_cuartel'
    id = db.Column(db.Integer, primary_key=True)
    bombero_numero = db.Column(db.String(20), db.ForeignKey('bomberos.numero'))
    hora_entrada = db.Column(db.DateTime, default=datetime.now)
    hora_salida = db.Column(db.DateTime)
    bombero = db.relationship('Bombero')

@login_manager.user_loader
def load_user(user_id): return db.session.get(Usuario, int(user_id))

# ==========================================
# --- RUTAS ---
# ==========================================

@app.context_processor
def inject_user(): return dict(user=current_user)

@app.template_filter('get_dotacion_completa')
def get_dotacion_completa(parte_id):
    return DotacionMovil.query.filter_by(parte_id=parte_id).all()


@app.route('/')
@login_required
def index():
    partes = ParteServicio.query.filter_by(estado="En curso").all()
    presentes = AsistenciaCuartel.query.filter(AsistenciaCuartel.hora_salida == None).all()
    
    # BUSCAMOS TODOS LOS LEGAJOS QUE ESTÁN EN SERVICIOS ACTIVOS
    legajos_ocupados = []
    for p in partes:
        # Buscamos en la dotación de cada parte activo
        dotacion = DotacionMovil.query.filter_by(parte_id=p.id).all()
        for d in dotacion:
            if d.bombero_numero:
                legajos_ocupados.append(str(d.bombero_numero))

    presentes_validos = [p for p in presentes if p.bombero is not None]
    
    return render_template('index.html', 
                           partes=partes, 
                           presentes=presentes_validos, 
                           total_presentes=len(presentes_validos), 
                           legajos_ocupados=legajos_ocupados) # <--- AHORA YA NO ESTÁ VACÍO


@app.route('/servicio/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_servicio():
    if request.method == 'POST':
        # Procesamos la hora que viene del formulario (HH:MM)
        hora_str = request.form.get('hora_denuncia_str')
        hora_final = datetime.now() # Por defecto ahora
        
        if hora_str:
            try:
                # Combinamos la fecha de hoy con la hora ingresada
                hoy = datetime.now().date()
                hora_dt = datetime.strptime(hora_str, '%H:%M').time()
                hora_final = datetime.combine(hoy, hora_dt)
            except Exception as e:
                print(f"Error al procesar hora: {e}")
                hora_final = datetime.now()

        nuevo = ParteServicio(
            nro_acta=request.form.get('nro_acta'),
            tipo_siniestro=request.form.get('tipo'),
            ubicacion=request.form.get('ubicacion'),
            denunciante_nombre=request.form.get('denunciante_nombre'),
            denunciante_tel=request.form.get('denunciante_tel'),
            hora_denuncia=hora_final, # Guardamos la hora exacta de la llamada
            hora_alarma=datetime.now(), # La alarma de salida es AHORA
            estado="En curso"
        )
        
        db.session.add(nuevo)
        db.session.commit()
        flash(f"🚨 Acta {nuevo.nro_acta} despachada correctamente.")
        return redirect(url_for('index'))
        
    return render_template('nuevo_servicio.html')

# ==========================================
# --- RUTAS CORREGIDAS PARA DOTACIÓN Y FINALIZAR ---
# ==========================================

@app.route('/admin')
@login_required
def admin_panel():
    if current_user.rol != 'Jefe':
        flash("Acceso denegado.")
        return redirect(url_for('index'))
    return render_template('admin_panel.html')

@app.route('/admin/partes')
@login_required
def admin_partes():
    if current_user.rol != 'Jefe':
        flash("Acceso denegado.")
        return redirect(url_for('index'))
    
    # Traemos todos los partes, ordenados por ID descendente (el último primero)
    todos_los_partes = ParteServicio.query.order_by(ParteServicio.id.desc()).all()
    return render_template('admin_partes.html', partes=todos_los_partes)

@app.route('/admin/moviles', methods=['GET', 'POST'])
@login_required
def admin_moviles():
    # Seguridad: Solo el Jefe puede gestionar la flota
    if current_user.rol != 'Jefe':
        flash("❌ Acceso denegado: Se requieren permisos de Jefatura.")
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        # ACCIÓN: NUEVO MÓVIL
        if 'nuevo' in request.form:
            nro = request.form.get('numero')
            desc = request.form.get('descripcion').upper()
            
            # Verificamos si el número ya existe para no duplicar
            existe = Movil.query.filter_by(numero=nro).first()
            if existe:
                flash(f"⚠️ El Móvil {nro} ya existe en el sistema.")
            else:
                nuevo_m = Movil(numero=nro, descripcion=desc, estado="Activo")
                db.session.add(nuevo_m)
                db.session.commit()
                flash(f"✅ Móvil {nro} dado de alta correctamente.")

        # ACCIÓN: CAMBIAR ESTADO (Baja/Alta)
        elif 'cambiar_estado' in request.form:
            m_id = request.form.get('movil_id')
            movil = db.session.get(Movil, m_id)
            if movil:
                nuevo_estado = "Baja" if movil.estado == "Activo" else "Activo"
                movil.estado = nuevo_estado
                db.session.commit()
                flash(f"🔄 Estado del Móvil {movil.numero} actualizado a {nuevo_estado}.")
            
        return redirect(url_for('admin_moviles'))

    # Traemos todos los móviles (Activos y de Baja) para la lista
    todos_los_moviles = Movil.query.order_by(Movil.numero).all()
    return render_template('admin_moviles.html', moviles=todos_los_moviles)

@app.route('/servicio/<int:parte_id>/gestion', methods=['GET', 'POST'])
@login_required
def cargar_dotacion(parte_id):
    obj_parte = db.session.get(ParteServicio, parte_id)
    
    if request.method == 'POST':
        # --- FORMULARIO 1: DATOS DE ENTRADA Y TÉCNICOS ---
        if 'guardar_informe' in request.form:
            # 1. Datos de la Denuncia (NUEVO: Ahora se pueden editar)
            obj_parte.denunciante_nombre = request.form.get('denunciante_nombre')
            obj_parte.denunciante_tel = request.form.get('denunciante_tel')
            
            h_den_str = request.form.get('hora_denuncia_str')
            if h_den_str:
                hoy = obj_parte.hora_alarma.date() # Usamos la fecha original del servicio
                hora_dt = datetime.strptime(h_den_str, '%H:%M').time()
                obj_parte.hora_denuncia = datetime.combine(hoy, hora_dt)

            # 2. Datos del Siniestro y Técnicos
            obj_parte.tipo_siniestro = request.form.get('tipo_siniestro')
            obj_parte.ubicacion = request.form.get('ubicacion')
            obj_parte.panorama = request.form.get('panorama')
            obj_parte.disposiciones = request.form.get('disposiciones')
            
            # 3. Personal Externo
            obj_parte.pol_movil = request.form.get('pol_movil')
            obj_parte.pol_cargo = request.form.get('pol_cargo')
            obj_parte.pol_obs = request.form.get('pol_obs')
            obj_parte.amb_movil = request.form.get('amb_movil')
            obj_parte.amb_cargo = request.form.get('amb_cargo')
            obj_parte.amb_obs = request.form.get('amb_obs')
            obj_parte.dc_movil = request.form.get('dc_movil')
            obj_parte.dc_cargo = request.form.get('dc_cargo')
            obj_parte.dc_obs = request.form.get('dc_obs')
            
            db.session.commit()
            flash("✅ Información del servicio actualizada.")
            return redirect(url_for('cargar_dotacion', parte_id=parte_id))

        # --- FORMULARIO 2: AÑADIR PERSONAL ---
        movil_db_id = request.form.get('movil_id') # Este es el ID de la tabla Movil
        bombero_id = request.form.get('bombero_id')
        rol_elegido = request.form.get('rol')

        if bombero_id and movil_db_id:
            # 1. VALIDACIÓN DE SEGURIDAD: ¿El bombero ya está asignado a este servicio?
            # Buscamos si ya existe en cualquier móvil de este mismo parte
            asignacion_previa = DotacionMovil.query.filter_by(parte_id=parte_id, bombero_numero=bombero_id).first()
            
            if asignacion_previa:
                # Si ya existe, obtenemos el número del móvil para avisar
                m_error = db.session.get(Movil, asignacion_previa.movil_id)
                nro_m = m_error.numero if m_error else "otro"
                flash(f"⚠️ ERROR: El bombero ya está asignado al Móvil {nro_m} en este servicio.")
                return redirect(url_for('cargar_dotacion', parte_id=parte_id))

            # 2. Entrada automática al cuartel si no está presente
            if not AsistenciaCuartel.query.filter_by(bombero_numero=str(bombero_id), hora_salida=None).first():
                db.session.add(AsistenciaCuartel(bombero_numero=str(bombero_id)))

            # 3. Guardar la nueva asignación
            # IMPORTANTE: Guardamos el ID del móvil que viene del SELECT
            nueva_dotacion = DotacionMovil(
                parte_id=parte_id,
                movil_id=movil_db_id, 
                bombero_numero=bombero_id,
                rol_en_unidad=rol_elegido
            )
            
            db.session.add(nueva_dotacion)
            db.session.commit()
            flash(f"👨‍🚒 Personal añadido correctamente.")
            return redirect(url_for('cargar_dotacion', parte_id=parte_id))

    # --- DATOS PARA RENDERIZAR LA PÁGINA ---
    dotacion_actual = DotacionMovil.query.filter_by(parte_id=parte_id).all()
    
    # Traemos los móviles activos de la DB para el desplegable
    moviles_lista = Movil.query.filter_by(estado="Activo").all()
    
    return render_template('dotacion.html', 
                           parte=obj_parte, 
                           servicio=obj_parte, 
                           bomberos=Bombero.query.all(),
                           moviles=moviles_lista,
                           dotacion=dotacion_actual)

@app.route('/eliminar_dotacion/<int:id>')
@login_required
def eliminar_dotacion(id):
    # Buscamos el registro en la base de datos
    registro = db.session.get(DotacionMovil, id)
    
    if registro:
        parte_id = registro.parte_id  # Guardamos el ID del parte para el redirect
        db.session.delete(registro)
        db.session.commit()
        flash("✅ Personal quitado de la dotación.")
        return redirect(url_for('cargar_dotacion', parte_id=parte_id))
    
    flash("❌ Error: No se encontró el registro.")
    return redirect(url_for('index'))

@app.route('/servicio/<int:id>/finalizar', methods=['GET', 'POST'])
@login_required
def finalizar_servicio(id):
    obj_parte = db.session.get(ParteServicio, id)
    
    if request.method == 'POST':
        obj_parte.panorama = request.form.get('panorama')
        obj_parte.tareas_realizadas = request.form.get('tareas')
        obj_parte.estado = "Finalizado"
        db.session.commit()
        return redirect(url_for('index'))
    
    # IMPORTANTE: Aquí también enviamos 'parte=obj_parte'
    return render_template('finalizar_servicio.html', parte=obj_parte)

@app.route('/asistencia', methods=['GET', 'POST'])
@login_required
def asistencia():
    if request.method == 'POST':
        legajo = request.form.get('bombero_id')
        accion = request.form.get('accion')
        if db.session.get(Bombero, str(legajo)):
            if accion == 'entrada':
                if not AsistenciaCuartel.query.filter_by(bombero_numero=str(legajo), hora_salida=None).first():
                    db.session.add(AsistenciaCuartel(bombero_numero=str(legajo)))
            elif accion == 'salida':
                reg = AsistenciaCuartel.query.filter_by(bombero_numero=str(legajo), hora_salida=None).first()
                if reg: reg.hora_salida = datetime.now()
            db.session.commit()
        return redirect(url_for('asistencia'))
    return render_template('asistencia.html', bomberos=Bombero.query.all(), presentes=AsistenciaCuartel.query.filter_by(hora_salida=None).all())


@app.route('/logout')
def logout():
    logout_user(); return redirect(url_for('login'))

@app.route('/monitor')
def monitor():
    # 1. Traemos los servicios que están "En curso"
    servicios = ParteServicio.query.filter_by(estado='En curso').all()
    
    # 2. Identificamos los legajos que están en la dotación de esos servicios
    legajos_en_servicio = []
    for s in servicios:
        dotacion = DotacionMovil.query.filter_by(parte_id=s.id).all()
        for d in dotacion:
            if d.bombero_numero:
                legajos_en_servicio.append(str(d.bombero_numero))
    
    # 3. Traemos a todos los que marcaron entrada y NO salida (Están en el cuartel)
    asistencias_activas = AsistenciaCuartel.query.filter_by(hora_salida=None).all()
    
    # 4. Filtramos: Solo los que están en el cuartel Y NO están en un servicio activo
    presentes = []
    for asis in asistencias_activas:
        if str(asis.bombero_numero) not in legajos_en_servicio:
            b = Bombero.query.get(str(asis.bombero_numero))
            if b:
                presentes.append(b)
    
    return render_template('monitor.html', servicios=servicios, presentes=presentes)

@app.route('/registrar_tiempo/<int:dotacion_id>/<tipo>')
@login_required
def registrar_tiempo(dotacion_id, tipo):
    reg = DotacionMovil.query.get_or_404(dotacion_id)
    ahora = datetime.now()
    
    # Buscamos a todos los bomberos que van en el mismo móvil para este servicio
    equipo = DotacionMovil.query.filter_by(parte_id=reg.parte_id, movil_id=reg.movil_id).all()
    
    for d in equipo:
        if tipo == 'salida':
            d.hora_salida = ahora
        elif tipo == 'siniestro':
            d.hora_llegada = ahora
        elif tipo == 'cuartel':
            d.hora_regreso = ahora
            
    db.session.commit()
    flash(f"Tiempo de {tipo} registrado para el Móvil {reg.movil.numero}")
    return redirect(url_for('gestionar_dotacion', parte_id=reg.parte_id))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = Usuario.query.filter_by(username=request.form['username']).first()
        if u and check_password_hash(u.password_hash, request.form['password']):
            login_user(u)
            return redirect(url_for('index'))
        flash('Usuario o clave incorrecta')
    return render_template('login.html')

# --- ESTO VA AL FINAL DE TU ARCHIVO DE 600+ LÍNEAS ---

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5001, debug=True)