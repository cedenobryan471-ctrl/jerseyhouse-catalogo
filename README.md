# JerseyHouse

Catálogo público y fotografías de portada.

## Disponibilidad desde el celular

1. Abrí `catalog.json` y buscá el nombre del producto. Copiá su `id`.
2. Abrí `estado.json` y tocá el lápiz para editar.
3. Agregá el identificador y su estado, conservando las comas entre entradas.
4. Guardá con Commit changes. Esperá a que termine la publicación.

Ejemplo:

```json
{
  "12345": "sold_out",
  "12346": "hidden",
  "12347": "active"
}
```

`sold_out`: agotado, visible pero no se puede pedir.
`hidden`: oculto de la tienda.
`active`: disponible.

Los cambios del panel anterior no modifican estos archivos. No incluyás contactos, direcciones web ni datos privados en los archivos públicos.
