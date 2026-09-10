# Incidente · 10-sep-2026 · la base aceptaba escritura anonima (RLS apagado)

**Gravedad**: alta — escritura y borrado anonimos sobre la base de la demo.
**Estado**: cerrado el 10-sep-2026 a las 15:37 UTC.
**Ventana de exposicion**: desde que se creo el esquema (9-sep ~21:00 UTC) hasta el cierre,
**~19 horas**.
**Datos afectados**: ninguno. Las tres tablas estaban vacias — el seed no existia todavia. La
unica fila que llego a existir fue la de la propia prueba, borrada en el mismo minuto.

## Que pasaba

`db/schema.sql` creaba `profiles`, `plans` e `intents` **sin activar row-level security**. En
Supabase eso no es inocuo: PostgREST publica cada tabla del esquema `public` en
`https://<ref>.supabase.co/rest/v1/`, la clave *publishable* es publica **por dise~no** (va en el
cliente) y la URL del proyecto esta versionada en `wrangler.jsonc`, en un repositorio **publico**.

Sin RLS, el rol `anon` conserva los permisos que Supabase le concede por defecto sobre `public`.
Resultado: cualquiera podia insertar, modificar o borrar filas de la demo.

## Como se comprobo

Insertando una fila real con la clave publica:

```
POST https://qbrgwphcpflbwhfqhffc.supabase.co/rest/v1/profiles
  apikey: <clave publishable>
→ HTTP 201 · [{"id":"…00ff","display_name":"PRUEBA RLS", …}]
```

Se borro inmediatamente despues.

## Causa raiz

El §5 del brief define el esquema y **no menciona RLS**, porque la regla 1 del proyecto dice
«MODO DEMO: sin auth real, sin RLS». Esa regla se leyo como «no hacen falta politicas de acceso»
cuando lo que significa es «no hay usuarios que autenticar».

**No son lo mismo.** Una base sin usuarios sigue necesitando estar cerrada: aqui el unico cliente
legitimo es el servidor de la propia demo, que usa la clave `secret` y salta RLS por dise~no.

La seccion J de la propuesta lo promete ademas explicitamente: *"Row-level security policies on
user data, tested as code"*.

## Que se hizo

1. Se borro la fila de prueba.
2. `alter table … enable row level security` en las tres tablas, **sin ninguna policy**: RLS sin
   policies deniega todo al rol anonimo y no estorba a `service_role`.
3. Se llevo al `db/schema.sql` para que sea reproducible, con el porque escrito al lado.
4. **Se probo como codigo**: `tests/rls.test.ts` verifica que un INSERT anonimo es rechazado y que
   un SELECT anonimo no devuelve filas. Ejecutado con credenciales reales: 2 tests en verde.

Verificado tras el cierre:

```
INSERT anonimo → HTTP 401 · new row violates row-level security policy for table "profiles"
SELECT anonimo → HTTP 200 · []
/api/salud     → {"estado":"ok","bd":"ok"}      (la app usa la clave de servidor)
```

## Que cambia para no repetirlo

- **Una tabla nace cerrada.** Cualquier tabla nueva de este proyecto lleva `enable row level
  security` en el mismo bloque que la crea.
- **«Sin auth» nunca significa «sin control de acceso».** Lo primero describe a los usuarios; lo
  segundo, a la superficie de red.
- El test de RLS se salta si no encuentra credenciales, **y lo dice**. Se ejecuta en local con las
  claves del proyecto; en CI no hay credenciales de Supabase a proposito.
