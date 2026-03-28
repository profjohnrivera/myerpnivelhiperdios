# backend/app/core/data_loader.py
import json
import csv
import asyncio
from pathlib import Path
from typing import Any, List, Dict, Optional
from app.core.registry import Registry
from app.core.env import Env

class DataLoader:
    """
    💿 MOTOR DE INGESTIÓN MASIVA (Versión Enterprise)
    Auto-descubre archivos en carpetas específicas y los sincroniza de forma idempotente.
    Soporta JSON para estructuras complejas y CSV para grandes volúmenes de datos.
    """
    
    # El orden es sagrado: Seguridad -> Datos Maestros -> Vistas
    LOAD_ORDER = ['security', 'data', 'views']

    @classmethod
    async def load_module_data(cls, app: Any, module_name: str, module_path: str):
        """
        Punto de entrada principal. Sincroniza el disco con el Grafo/DB.
        """
        base_path = Path(module_path)
        if not base_path.exists():
            return

        # Inicializamos el entorno de sistema para tener acceso total
        env = Env(user_id="system", graph=app.graph)
        IrModelData = env['ir.model.data']

        for folder_name in cls.LOAD_ORDER:
            folder_path = base_path / folder_name
            if not folder_path.exists() or not folder_path.is_dir():
                continue

            # Filtramos solo archivos compatibles
            files = sorted(folder_path.glob("*.*"))
            valid_files = [f for f in files if f.suffix in ['.json', '.csv']]
            
            for file_path in valid_files:
                print(f"   💿 Ingestando: [{module_name}] -> {folder_name}/{file_path.name}")
                await cls._process_file(app, env, IrModelData, module_name, file_path)

    @classmethod
    async def _process_file(cls, app: Any, env: Env, IrModelData: Any, module_name: str, file_path: Path):
        """Traduce archivos físicos a una estructura de registros unificada."""
        raw_records = []
        
        if file_path.suffix == '.json':
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_records = json.load(f)
                
        elif file_path.suffix == '.csv':
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    metadata = {
                        'id': row.pop('id'),
                        'model': row.pop('model'),
                        'noupdate': str(row.pop('noupdate', 'false')).lower() == 'true'
                    }
                    fields = {k: cls._parse_csv_val(v) for k, v in row.items() if v}
                    raw_records.append({**metadata, 'fields': fields})

        # Procesamiento atómico de cada registro
        for rec in raw_records:
            await cls._sync_record(app, env, IrModelData, module_name, rec)

    @classmethod
    async def _sync_record(cls, app: Any, env: Env, IrModelData: Any, module_name: str, rec_data: Dict):
        """
        Sincroniza un registro aplicando lógica de External IDs para evitar duplicados.
        """
        xml_id = f"{module_name}.{rec_data['id']}"
        model_name = rec_data['model']
        fields = rec_data.get('fields', {})
        noupdate = rec_data.get('noupdate', False)

        # 1. Resolución de Relaciones: Convierte 'base.res_company_1' -> UUID físico
        await cls._resolve_relations(IrModelData, fields, xml_id)

        # 2. Búsqueda de Identidad Previa
        res_id = await IrModelData.get_id(xml_id)
        TargetModel = env[model_name]

        if res_id:
            # 🔄 ACTUALIZACIÓN (Si el mapeo existe)
            # Verificamos si el registro en ir.model.data permite actualizaciones
            mapping_records = await IrModelData.search([
                ('module', '=', module_name), 
                ('name', '=', rec_data['id'])
            ])
            
            if mapping_records and not mapping_records[0].noupdate:
                # Instanciamos el registro existente y escribimos cambios
                record = TargetModel(_id=res_id, context=app.graph)
                await record.write(fields)
        else:
            # ✨ CREACIÓN (Nuevo registro)
            new_record = await TargetModel.create(fields)
            
            # Registramos el mapeo oficial en el sistema
            await IrModelData.create({
                'module': module_name,
                'name': rec_data['id'],
                'model_name': model_name,
                'res_id': new_record.id,
                'noupdate': noupdate
            })
            # Inyectamos en la caché inmediata del contexto
            IrModelData.set_cache(xml_id, new_record.id)

    @staticmethod
    async def _resolve_relations(IrModelData: Any, fields: Dict, current_xml_id: str):
        """
        Interpreta los valores del archivo. Si detecta un xml_id, lo traduce a UUID.
        Soporta Many2one y X2many (listas).
        """
        for k, v in fields.items():
            if isinstance(v, str) and IrModelData.is_xml_id(v):
                ref_id = await IrModelData.get_id(v)
                if not ref_id:
                    raise ValueError(f"❌ Error en {current_xml_id}: La referencia '{v}' no existe.")
                fields[k] = ref_id
            
            elif isinstance(v, list):
                # Resolución para listas de IDs (Many2many / One2many)
                resolved_list = []
                for item in v:
                    if isinstance(item, str) and IrModelData.is_xml_id(item):
                        ref_id = await IrModelData.get_id(item)
                        if not ref_id:
                            raise ValueError(f"❌ Error en {current_xml_id}: Referencia de lista '{item}' no hallada.")
                        resolved_list.append(ref_id)
                    else:
                        resolved_list.append(item)
                fields[k] = resolved_list

    @staticmethod
    def _parse_csv_val(v: str) -> Any:
        """Helper para parsear tipos de datos desde el string plano del CSV."""
        v_lower = v.lower()
        if v_lower == 'true': return True
        if v_lower == 'false': return False
        if v.startswith('[') or v.startswith('{'):
            try: return json.loads(v.replace("'", '"'))
            except: return v
        return v