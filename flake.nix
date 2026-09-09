{
  description = "Node / Nuxt / Vue / TypeScript -> Cloudflare Workers";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  outputs = { self, nixpkgs }:
    let
      # Multi-sistema (ADR-0008): la MISMA configuracion en la dev instance aarch64 y en
      # cualquier maquina x86_64 (GCP, runners de CI). La identidad la da el flake.lock.
      sistemas = [ "aarch64-linux" "x86_64-linux" ];
      porSistema = f: nixpkgs.lib.genAttrs sistemas (system: f nixpkgs.legacyPackages.${system});
    in {
      devShells = porSistema (pkgs: {
        default = pkgs.mkShell {
        packages = with pkgs; [
          just
          nodejs_22
          pnpm
          typescript
          typescript-language-server
          vscode-langservers-extracted   # LSP de eslint, html, css, json
          biome                          # linter y formatter
          # wrangler de nixpkgs (4.93.0) va MUY por detras de npm (4.120.0) y le falta
          # 'login --device', el unico flujo headless que sirve sin navegador.
          # EL PROYECTO YA LO DECLARA: el esqueleto trae `"wrangler": "catalog:"` y la version
          # vive en `pnpm-workspace.yaml`. Este de aqui es solo el respaldo para un shell
          # suelto — `pnpm exec wrangler` resuelve al del proyecto, que es el que manda.
          wrangler
          supabase-cli                   # OJO: pinear, ver LEEME.md (el 'start' se rompe en >=2.112.0)
         gitleaks ];
        shellHook = ''
          export npm_config_store_dir="/workspace/.cache/pnpm"

          # WRANGLER_HOME NO EXISTE en wrangler 4.x (verificado: solo aparece en source-maps).
          # Lo que si respeta es WRANGLER_CACHE_DIR. Y como aqui autenticamos por
          # CLOUDFLARE_API_TOKEN (no por OAuth), no hay estado de sesion que persistir.
          export WRANGLER_CACHE_DIR="/workspace/.cache/wrangler"
          mkdir -p "$WRANGLER_CACHE_DIR"

          # El Supabase CLI habla la API de Docker; aqui la sirve podman rootless.
          export DOCKER_HOST="unix:///run/user/$(id -u)/podman/podman.sock"
          # Sin esto 'supabase stop --no-backup' falla: manda el filtro all=true a
          # volumes/prune con API >=1.42 y podman lo rechaza con HTTP 500.
          export DOCKER_API_VERSION=1.41

          echo "Node $(node --version) | pnpm $(pnpm --version) | wrangler $(wrangler --version 2>/dev/null | tail -1) | supabase $(supabase --version 2>/dev/null | tail -1)"
        '';
        };
      });
    };
}
