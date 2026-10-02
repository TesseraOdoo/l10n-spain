Este módulo implementa el **DeCA** (_Documento electrónico de Control Administrativo_),
el documento de control que debe acompañar a todo transporte público de mercancías por
carretera en España desde el 5 de octubre de 2026.

Normativa en la que se basa la implementación:

- [Orden FOM/2861/2012](https://www.boe.es/buscar/act.php?id=BOE-A-2013-154), que regula
  el documento de control y fija su contenido mínimo (artículo 6).
- [Resolución de 5 de junio de 2026](https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-12784)
  de la Dirección General de Transporte por Carretera y Ferrocarril, que fija los
  requisitos técnicos del DeCA: fichero PDF con código QR, descarga pública, metadatos,
  conservación y modificación de datos durante el servicio.
- [Información del Ministerio de Transportes sobre el DeCA](https://www.transportes.gob.es/transporte-terrestre/profesionales-transporte/servicios-transportista/documento-electronico-control-administrativo-deca).

Para cada albarán de salida aporta:

- Los datos de transporte que exige el artículo 6 de la Orden FOM/2861/2012: cargador
  contractual, transportista efectivo, lugar de origen y de destino, naturaleza y peso
  bruto de la mercancía, fecha del transporte, matrículas del vehículo y del remolque,
  autorización especial de circulación y observaciones.
- La emisión del DeCA como fichero PDF, con un código QR que apunta a una URL pública y
  única de la propia instancia de Odoo desde la que se descarga el fichero directamente,
  sin autenticación. La instancia debe ser accesible por HTTPS para que el QR sea
  válido. Los metadatos del PDF recogen la fecha de creación de la primera versión y la
  de modificación de la última.
- **Versiones**: cada emisión guarda el fichero PDF junto con una instantánea inmutable
  de los datos impresos. Si los datos cambian durante el servicio se emite una nueva
  versión indicando el motivo del cambio; la URL y el QR se mantienen, los valores
  sustituidos se imprimen tachados y los ficheros anteriores se conservan, según el
  apartado Quinto de la Resolución.
- Un plazo configurable tras la entrega durante el cual la descarga pública sigue
  disponible (siete días por defecto, según permite la normativa).

Los ficheros emitidos quedan ligados a cada versión, no pueden borrarse y constituyen el
repositorio que exige la normativa; se conservan mientras exista el albarán, lo que
cubre el año mínimo de conservación.
