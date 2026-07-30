# Runway MCP Server

Documentation pour connecter et utiliser le serveur **MCP (Model Context Protocol) de Runway**,
qui permet à un agent IA (Claude, Cursor, ChatGPT, etc.) de générer des images, des vidéos et de
l'audio via Runway sans quitter l'outil.

> Cas d'usage pour ce projet (`jeu-voiture-`) : générer des assets visuels — voitures, décors,
> textures, vidéos promotionnelles ou effets — directement depuis l'agent.

---

## 1. Endpoint

| | |
|---|---|
| **URL du serveur hébergé** | `https://mcp.runwayml.com/mcp` |
| **Transport** | Streamable HTTP (HTTP distant) |
| **Hébergement** | Serveur officiel géré par Runway (aucune installation locale requise) |

Il existe deux façons d'utiliser Runway via MCP :

1. **Serveur hébergé (recommandé)** — l'URL ci-dessus. Connexion par OAuth ou clé API.
2. **Serveur auto-hébergé** — le dépôt open source [`runwayml/runway-api-mcp-server`](https://github.com/runwayml/runway-api-mcp-server),
   à lancer en local (extension Claude Desktop) ou à déployer soi-même (Railway, tunnel, etc.).

> ⚠️ Ne pas confondre avec `https://mcp.runway.team` — c'est le MCP de *Runway* (gestion de
> projet), un produit différent. Ici on parle bien de **RunwayML** (génération d'images/vidéos).

---

## 2. Authentification

Deux options, l'accès aux différents outils dépendant des *scopes* de la clé :

- **OAuth** — se connecter avec son compte Runway. L'usage et la facturation sont rattachés au
  plan Runway existant. C'est le flux le plus simple pour le serveur hébergé.
- **Clé API (Bearer token)** — créer une clé sur <https://dev.runwayml.com> (compte développeur +
  facturation configurée requis). La clé est envoyée dans l'en-tête `Authorization: Bearer <clé>`.

> 🕒 **Important** : les médias générés via l'API Runway ne sont accessibles à leur URL que
> pendant **24 heures**. Télécharger/archiver les fichiers rapidement.

---

## 3. Connexion depuis un client

### Claude Code (CLI)

```bash
claude mcp add --transport http runway https://mcp.runwayml.com/mcp
```

Puis lancer l'authentification OAuth depuis Claude Code :

```
/mcp
```

et suivre le flux de connexion pour `runway`.

### Claude Desktop / clients à config JSON

Serveur hébergé (HTTP distant) :

```json
{
  "mcpServers": {
    "runway": {
      "type": "http",
      "url": "https://mcp.runwayml.com/mcp"
    }
  }
}
```

Serveur auto-hébergé (clé API en variable d'environnement) :

```json
{
  "mcpServers": {
    "runway-api-mcp-server": {
      "command": "node",
      "args": ["<CHEMIN>/build/index.js"],
      "env": {
        "RUNWAYML_API_SECRET": "<VOTRE_CLÉ>",
        "MCP_TOOL_TIMEOUT": "1000000"
      }
    }
  }
}
```

### Cursor / ChatGPT / autres

Tout client compatible MCP fonctionne. Ajouter un serveur MCP distant de type HTTP pointant vers
`https://mcp.runwayml.com/mcp` et s'authentifier via OAuth.

---

## 4. Outils exposés

Noms tels qu'exposés par le serveur open source (le serveur hébergé propose ces outils et
davantage) :

| Outil | Rôle |
|---|---|
| `runway_listModels` | Liste les modèles disponibles par capacité et le modèle par défaut recommandé |
| `runway_generateImage` | Génère une image à partir d'un prompt texte et d'images de référence optionnelles |
| `runway_generateVideo` | Génère une vidéo à partir d'une image + un prompt texte |
| `runway_editVideo` | Édite une vidéo, avec images de référence optionnelles |
| `runway_upscaleVideo` | Augmente la résolution d'une vidéo |
| `runway_generateAudio` | Synthèse vocale (text-to-speech) à partir de texte |
| `runway_getTask` | Récupère les détails d'une tâche (statut, résultat) |
| `runway_cancelTask` | Annule ou supprime une tâche |
| `runway_getOrg` | Informations sur l'organisation |

> La génération est **asynchrone** : un appel `generate*` renvoie un identifiant de tâche, puis on
> interroge `runway_getTask` jusqu'à obtention du résultat.

---

## 5. Exemple de flux

1. `runway_listModels` — voir les modèles disponibles pour l'image.
2. `runway_generateImage` avec un prompt (ex. *"voiture de course rouge, vue 3/4, fond studio,
   style low-poly"*) → renvoie un `taskId`.
3. `runway_getTask` avec ce `taskId` → récupérer l'URL de l'image générée.
4. Télécharger le média **dans les 24 h** et l'ajouter aux assets du jeu.

---

## Variables d'environnement (serveur auto-hébergé)

| Variable | Rôle |
|---|---|
| `RUNWAYML_API_SECRET` | Clé API (fallback en déploiement, requise en local) |
| `REQUIRE_AUTH` | `true` pour un déploiement multi-tenant (force le Bearer token du client) |
| `PORT` | Port d'écoute (injecté automatiquement par Railway) |
| `MCP_TOOL_TIMEOUT` | Timeout des outils en millisecondes |

---

## Ressources

- Serveur MCP hébergé : <https://mcp.runwayml.com/mcp>
- Annonce officielle : <https://runwayml.com/news/mcp>
- Dépôt open source : <https://github.com/runwayml/runway-api-mcp-server>
- Portail développeur / clés API : <https://dev.runwayml.com>
- Documentation Runway : <https://help.runwayml.com>
