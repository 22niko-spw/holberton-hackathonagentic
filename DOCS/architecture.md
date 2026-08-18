---
config:
  layout: elk
---
flowchart TB
 subgraph FRONT["FRONTEND — Interface d'approbation"]
        UI["Saisie intention<br>langage naturel"]
        Gate{"Plan affiche<br>validation action par action"}
        JournalUI@{ label: "Journal d'audit<br>consultation + annulation" }
  end
 subgraph AGENT["COUCHE AGENT"]
        API["API / Serveur"]
        AgentLoop["Boucle Agent"]
        LLM["Modele LLM<br>+ system prompt"]
  end
 subgraph BACK["BACKEND"]
        Exec["Executeur idempotent<br>actions approuvees uniquement"]
  end
 subgraph TOOLS["COUCHE OUTILS — effets de bord"]
        Real["create_issue<br>GitHub reel"]
        Mock["send_message / create_account<br>create_calendar_event<br>mockes"]
  end
 subgraph STORAGE["STOCKAGE"]
        GH["GitHub API<br>systeme externe reel"]
        Outbox["/Outbox + fichiers mock/"]
        DB[("SQLite<br>metier + audit")]
  end
    User(["Utilisateur RH"]) --> UI
    UI --> API
    API --> AgentLoop
    AgentLoop <--> LLM
    AgentLoop --- Gate
    Gate -- approuve --> Exec
    Gate -- refuse --> JournalUI
    Exec --> Real & Mock
    Real --> GH
    Mock --> Outbox
    Exec -- trace chaque action --> DB
    DB --> JournalUI
    JournalUI -. annuler derniere action .-> Exec

    JournalUI@{ shape: rect}
     UI:::frontStyle
     Gate:::gateStyle
     JournalUI:::frontStyle
     API:::agentStyle
     AgentLoop:::agentStyle
     LLM:::agentStyle
     Exec:::backStyle
     Real:::toolsStyle
     Mock:::toolsStyle
     GH:::storageStyle
     Outbox:::storageStyle
     DB:::storageStyle
    classDef gateStyle fill:#ffe0e0,stroke:#d00,stroke-width:2px
    classDef frontStyle fill:#eef2ff,stroke:#818cf8,stroke-width:1px
    classDef agentStyle fill:#f0fdfa,stroke:#2dd4bf,stroke-width:1px
    classDef backStyle fill:#fff7ed,stroke:#fb923c,stroke-width:1px
    classDef toolsStyle fill:#fdf4ff,stroke:#e879f9,stroke-width:1px
    classDef storageStyle fill:#f0fdf4,stroke:#4ade80,stroke-width:1px