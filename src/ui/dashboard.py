import customtkinter as ctk

class DashboardFrame(ctk.CTkFrame):
    def __init__(self, parent, config_manager, controller):
        super().__init__(parent, fg_color="transparent")
        self.config_manager = config_manager
        self.controller = controller
        
        self.grid_columnconfigure((0, 1), weight=1)
        
        title = ctk.CTkLabel(self, text="Dashboard", font=ctk.CTkFont(size=28, weight="bold"))
        title.grid(row=0, column=0, columnspan=2, pady=(20, 30), sticky="w", padx=20)
        
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20)
        stats_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        self.card_clients = ctk.CTkFrame(stats_frame, corner_radius=15, fg_color=("white", "gray20"), border_width=1, border_color=("gray85", "gray15"))
        self.card_clients.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(self.card_clients, text="Gesamte Kunden", font=ctk.CTkFont(size=14)).pack(pady=(15, 5))
        self.lbl_client_count = ctk.CTkLabel(self.card_clients, text="-", font=ctk.CTkFont(size=32, weight="bold"))
        self.lbl_client_count.pack(pady=(0, 15))
        
        self.card_backup = ctk.CTkFrame(stats_frame, corner_radius=15, fg_color=("white", "gray20"), border_width=1, border_color=("gray85", "gray15"))
        self.card_backup.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(self.card_backup, text="Letztes Backup", font=ctk.CTkFont(size=14)).pack(pady=(15, 5))
        self.lbl_last_backup = ctk.CTkLabel(self.card_backup, text="-", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_last_backup.pack(pady=(10, 15))
        
        self.card_recent = ctk.CTkFrame(stats_frame, corner_radius=15, fg_color=("white", "gray20"), border_width=1, border_color=("gray85", "gray15"))
        self.card_recent.grid(row=0, column=2, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(self.card_recent, text="Zuletzt verwendet", font=ctk.CTkFont(size=14)).pack(pady=(15, 5))
        self.lbl_recent_clients = ctk.CTkLabel(self.card_recent, text="-", font=ctk.CTkFont(size=14))
        self.lbl_recent_clients.pack(pady=(0, 15))
        
    def refresh(self):
        stats = self.controller.get_dashboard_stats()
        self.lbl_client_count.configure(text=str(stats.get("client_count", 0)))
        self.lbl_last_backup.configure(text=stats.get("last_backup", "Nie"))
        
        recent = self.config_manager.get("recent_clients", [])
        if recent:
            self.lbl_recent_clients.configure(text="\n".join(recent))
        else:
            self.lbl_recent_clients.configure(text="Keine")
