# backend/modules/core_system/models/ir_module.py
from app.core.orm import Model, Field, SelectionField, One2manyField, RelationField, compute, check_state
from app.core.decorators import action, transaction
from app.core.registry import Registry
from app.core.env import Context

class IrModule(Model):
    """
    📦 GESTOR DE APLICACIONES (ir.module)
    Controla qué partes del ERP están activas, instaladas o por actualizar.
    """
    _name = 'ir.module'
    _rec_name = 'shortdesc'

    name = Field(type_='string', label='Nombre Técnico (Carpeta)', required=True, index=True)
    shortdesc = Field(type_='string', label='Nombre Público')
    summary = Field(type_='string', label='Resumen')
    version = Field(type_='string', default='1.0', label='Versión Instalada')
    author = Field(type_='string', default='Automata', label='Autor')
    
    state = SelectionField(
        options=['uninstalled', 'installed', 'to install', 'to upgrade', 'to remove'],
        default='uninstalled',
        label='Estado'
    )
    
    # Flags avanzados
    auto_install = Field(type_='bool', default=False, label='Auto Instalable')
    application = Field(type_='bool', default=False, label='Es Aplicación Principal')
    
    # Relaciones
    dependency_ids = One2manyField('ir.module.dependency', label='Dependencias')

    # =========================================================
    # ACCIONES DE ESTADO (Transaccionales y Seguras)
    # =========================================================

    @action(label="Instalar", icon="download", variant="primary")
    @check_state(['uninstalled'])
    @transaction 
    async def button_install(self):
        """Marca el módulo y sus dependencias para instalación."""
        # 1. Buscar dependencias recursivamente
        IrModuleDependency = Registry.get_model('ir.module.dependency')
        # Buscamos quiénes son mis dependencias
        deps = await IrModuleDependency.search([('module_id', '=', self.id)])
        
        for dep in deps:
            # Intentamos resolver el ID del módulo objetivo por su nombre técnico
            IrModule = Registry.get_model('ir.module')
            target_mod = await IrModule.search([('name', '=', dep.name)])
            
            if target_mod:
                # Si la dependencia no está instalada, la mandamos a instalar recursivamente
                if target_mod.state == 'uninstalled':
                    await target_mod.button_install()
            else:
                raise ValueError(f"❌ Imposible instalar '{self.name}'. Falta la dependencia física '{dep.name}'.")

        # 2. Cambiar estado
        await self.write({'state': 'to install'})
        print(f"   📦 Módulo '{self.name}' encolado para INSTALACIÓN.")

    @action(label="Desinstalar", icon="trash", variant="danger", confirm="¿Seguro que desea desinstalar?")
    @check_state(['installed', 'to upgrade'])
    @transaction
    async def button_uninstall(self):
        """Marca para desinstalación y arrastra a los que dependen de él (Cascada)"""
        # 1. Buscar quién depende de MÍ (Downstream)
        IrModuleDependency = Registry.get_model('ir.module.dependency')
        downstream_deps = await IrModuleDependency.search([('name', '=', self.name)])
        
        for dep in downstream_deps:
            parent_module = dep.module_id # El módulo que me tiene como dependencia
            if parent_module.state in ['installed', 'to upgrade', 'to install']:
                print(f"   ⚠️ Arrastrando módulo '{parent_module.name}' a desinstalación por dependencia...")
                await parent_module.button_uninstall()

        # 2. Marcar para remoción
        await self.write({'state': 'to remove'})
        print(f"   🗑️ Módulo '{self.name}' encolado para DESINSTALACIÓN.")

    @action(label="Cancelar Operación", icon="x")
    @check_state(['to install', 'to upgrade', 'to remove'])
    async def button_cancel(self):
        """Revierte los estados transitorios."""
        new_state = 'uninstalled' if self.state == 'to install' else 'installed'
        await self.write({'state': new_state})


class IrModuleDependency(Model):
    """
    🔗 DEPENDENCIAS DE MÓDULOS (ir.module.dependency)
    Mapea las relaciones técnicas entre carpetas de módulos.
    """
    _name = 'ir.module.dependency'

    module_id = RelationField('ir.module', label='Módulo Padre', required=True, ondelete='cascade')
    name = Field(type_='string', label='Nombre Técnico Dependencia', required=True, index=True)
    
    # 💎 MEJORA REACTIVA: Calculamos el estado del módulo objetivo en tiempo real
    depend_id = RelationField('ir.module', label='Módulo Objetivo')
    state = Field(type_='string', label='Estado Objetivo', readonly=True)

    @compute(depends=['name'])
    async def _compute_state(self):
        """Busca el estado actual del módulo al que apunta esta dependencia."""
        IrModule = Registry.get_model('ir.module')
        target = await IrModule.search([('name', '=', self.name)])
        if target:
            self.state = target.state
            # Si no estaba vinculado, lo vinculamos para navegación rápida
            if not self.depend_id:
                self.depend_id = target.id
        else:
            self.state = 'missing'