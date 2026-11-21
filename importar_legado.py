"""Importación optativa de SQLite anterior, idempotente y SIN contraseñas."""
import hashlib
import sqlite3
from datetime import date
from decimal import Decimal,InvalidOperation
from pathlib import Path
from django.core.management.base import BaseCommand,CommandError
from django.core.exceptions import ValidationError
from django.db import transaction
from core.models import (Usuario,Categoria,Movimiento,Presupuesto,Ahorro,AportacionAhorro,RegistroImportacion)
from core.services import actualizar_alertas

class Command(BaseCommand):
    help='Revisa o importa registros financieros del SQLite anterior sin tocar cuentas ni contraseñas.'
    def add_arguments(self,parser):
        parser.add_argument('--ruta',required=True,help='Ruta de db.sqlite3 del proyecto original')
        parser.add_argument('--apply',action='store_true',help='Aplica los datos (sin esta opción es simulación)')

    def handle(self,*args,**opts):
        path=Path(opts['ruta']).expanduser().resolve()
        if not path.is_file() or path.suffix.lower() not in ('.sqlite3','.sqlite','.db'):raise CommandError('Archivo SQLite no encontrado.')
        if path.resolve()==Path('db.sqlite3').resolve():raise CommandError('No se puede importar sobre la misma base activa.')
        stamp=hashlib.sha256(str(path).encode()).hexdigest()[:20]
        # Apertura en modo solo lectura, sin modificar nunca el archivo fuente.
        from urllib.parse import quote
        old=sqlite3.connect('file:'+quote(str(path))+'?mode=ro',uri=True)
        old.row_factory=sqlite3.Row
        try:
            existing={x[0] for x in old.execute("select name from sqlite_master where type='table'")}
            required={'core_usuario','core_categoria','core_movimiento','core_presupuesto','core_ahorro'}
            if not required <= existing:raise CommandError('El archivo no contiene el esquema esperado del proyecto original.')
            olds={r['id']:Usuario.objects.filter(email__iexact=(r['email'] or '')).first() for r in old.execute('select id,email from core_usuario')}
            matches=sum(bool(u) for u in olds.values())
            self.stdout.write(f'Usuarios con correo coincidente: {matches} de {len(olds)}. Cuentas y contraseñas NO se importan.')
            cids={};importe_legacy=0; saltadas=0
            with transaction.atomic():
                for r in old.execute('select * from core_categoria order by id'):
                    u=olds.get(r['usuario_id']) if r['usuario_id'] else None
                    if r['usuario_id'] and not u: continue
                    c=Categoria.objects.filter(usuario=u,nombre=r['nombre'],tipo=r['tipo']).first()
                    if not c and opts['apply']:
                        try:
                            c=Categoria(usuario=u,nombre=r['nombre'],tipo=r['tipo'],clasificacion=r['clasificacion'],activa=bool(r['activa']))
                            c.full_clean();c.save()
                        except ValidationError: c=None
                    if c:cids[r['id']]=c
                for r in old.execute('select * from core_movimiento order by fecha,id'):
                    u=olds.get(r['usuario_id'])
                    c=cids.get(r['categoria_id'])
                    clave=f'{stamp}:movimiento:{r["id"]}'
                    if not u or not c or RegistroImportacion.objects.filter(clave=clave).exists(): saltadas+=1;continue
                    if not opts['apply']:
                        importe_legacy+=1;continue
                    try:
                        m=Movimiento(usuario=u,categoria=c,tipo=r['tipo'],importe=Decimal(str(r['importe'])),fecha=date.fromisoformat(r['fecha']),descripcion=r['descripcion'],origen='NORMAL')
                        m.full_clean();m.save();RegistroImportacion.objects.create(clave=clave);importe_legacy+=1
                    except (ValidationError,InvalidOperation,ValueError):saltadas+=1
                if opts['apply']:
                    # Presupuestos y metas se importan sin forzar relaciones de fuentes inexistentes.
                    for r in old.execute('select * from core_presupuesto order by id'):
                        u=olds.get(r['usuario_id']);c=cids.get(r['categoria_id']) if r['categoria_id'] else None
                        clave=f'{stamp}:presupuesto:{r["id"]}'
                        if not u or (r['categoria_id'] and not c) or RegistroImportacion.objects.filter(clave=clave).exists():continue
                        try:
                            p=Presupuesto(usuario=u,nombre=f'Presupuesto importado #{r["id"]}',categoria=c,monto_limite=Decimal(str(r['monto_limite'])),periodo=r['periodo'],fecha_inicio=date.fromisoformat(r['fecha_inicio']),fecha_fin=date.fromisoformat(r['fecha_fin']))
                            p.full_clean();p.save();RegistroImportacion.objects.create(clave=clave)
                        except (ValidationError,ValueError,InvalidOperation):saltadas+=1
                    for r in old.execute('select * from core_ahorro order by id'):
                        u=olds.get(r['usuario_id']); clave=f'{stamp}:ahorro:{r["id"]}'
                        if not u or RegistroImportacion.objects.filter(clave=clave).exists():continue
                        try:
                            a=Ahorro(usuario=u,titulo=r['titulo'],monto_objetivo=Decimal(str(r['monto_objetivo'])),porcentaje_sugerido=r['porcentaje_sugerido'],fecha_limite=(date.fromisoformat(r['fecha_limite']) if r['fecha_limite'] else None))
                            a.full_clean();a.save()
                            reservado=Decimal(str(r['monto_actual']))
                            if reservado>0:AportacionAhorro.objects.create(ahorro=a,importe=reservado)
                            RegistroImportacion.objects.create(clave=clave)
                        except (ValidationError,ValueError,InvalidOperation):saltadas+=1
                    for u in {u.pk:u for u in olds.values() if u}.values():actualizar_alertas(u)
            modo='REGISTROS IMPORTADOS' if opts['apply'] else 'MOVIMIENTOS ELEGIBLES (simulación)'
            self.stdout.write(self.style.SUCCESS(f'{modo}: {importe_legacy}; omitidos/repetidos: {saltadas}.'))
            if not opts['apply']:self.stdout.write('No se modificó la base nueva. Usa --apply para confirmar la importación.')
        finally:old.close()
