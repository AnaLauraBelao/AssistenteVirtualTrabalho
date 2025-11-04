from pprint import pprint

import discord

from src.utils.google_drive import alter_cell_text
from src.utils.infisical import get_secret
from src.utils.teamwork import get_task_by_id


class ActivitiesSelect(discord.ui.Select):
    MAX_LABEL = 100

    @staticmethod
    def _clip(text: str, limit: int = 100) -> str:
        return text if len(text) <= limit else text[:limit]

    def __init__(self, activities_map: dict[str, str]):
        # activities_map: {"<id>": "Nome da atividade"}
        options = [
            discord.SelectOption(label=self._clip(name, self.MAX_LABEL), value=act_id)
            for act_id, name in activities_map.items()
        ]
        super().__init__(
            placeholder="Selecione uma atividade",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        view: ActivitiesView = self.view  # type: ignore

        if len(view.activities) <= view.limit_by_page:
            await view.edit_button_state(custom_id="next_page", new_disabled=True)

        if interaction.user.id != view.author_id:
            await interaction.response.send_message(
                "Apenas quem iniciou pode interagir com esta seleção.",
                ephemeral=True
            )
            return

        selected_id = self.values[0]
        selected_name = view.available[selected_id]

        # Atualiza os selecionados
        view.selected_ids.append(selected_id)
        view.selected_names_by_id[selected_id] = selected_name

        task = get_task_by_id(selected_id)

        projects = task['included']['projects']

        # Pegando o primeiro (ou único) projeto
        project_key, project_data = next(iter(projects.items()))

        # id e name
        project_id = project_data.get('id', project_key)  # cai no key se o campo 'id' não existir
        project_name = project_data.get('name')

        if project_id not in view.selected_tasks:
            view.selected_tasks[project_id] = {
                'project_name': project_name,
                'tasks': []
            }

        view.selected_tasks[project_id]['tasks'].append({
            'id': selected_id,
            'name': selected_name,
        })

        # view.selected_tasks[task['included']['projects']] =

        # Remove dos disponíveis
        del view.available[selected_id]
        for activity in view.activities:
             if activity['id'] == int(selected_id):
                 view.activities.remove(activity)
                 break

        if len(view.activities) == 0:
            view.remove_item(self)  # Remove o seletor da View
            view.last_text = "Não há mais atividades disponíveis."
            await view.finalizar_interacao(interaction)
            return


        start = view.limit_by_page * (view.page - 1)
        end = view.limit_by_page * view.page
        paginated_activities = view.activities[start:end]


        if len(paginated_activities) < 1:
            view.page = view.page - 1
            start = view.limit_by_page * (view.page - 1)
            end = view.limit_by_page * view.page
            paginated_activities = view.activities[start:end]

        if view.page > 0:
            view.available = {str(a["id"]): a["name"] for a in paginated_activities}


        if view.page <= 1:
            await view.edit_button_state(custom_id="previous_page", new_disabled=True)

        if view.limit_by_page * view.page >= len(view.activities):
            await view.edit_button_state(custom_id="next_page", new_disabled=True)

        # Recria as opções restantes no combobox (truncando apenas o label)
        self.options = [
            discord.SelectOption(label=self._clip(name, self.MAX_LABEL), value=act_id)
            for act_id, name in view.available.items()
        ]

        # Desabilita se acabou a lista
        self.disabled = len(self.options) == 0

        # Feedback e atualização da View
        resumo = f"Selecionado: {selected_name} (id: {selected_id})\n" \
                 f"Restantes: {len(view.activities)}\n" \
                 f"Selecionados até agora: {len(view.selected_ids)}"
        view.last_text = resumo
        await interaction.response.edit_message(content=resumo, view=view)


class ActivitiesView(discord.ui.View):
    def __init__(self, author_id: int, activities: list[dict], timeout: float | None = 300, planning_name: str = "", day_value: str = "", page: int = 1, last_text: str = "Selecione uma atividade no combobox. Clique em Finalizar quando terminar."):
        super().__init__(timeout=timeout)
        self.selected_tasks = {}
        self.author_id = author_id
        self.planning_name = planning_name
        self.day_value = day_value
        self.last_text = last_text

        # Mapa de disponíveis e estruturas para resultados
        self.page = page
        self.activities = activities
        self.limit_by_page: int = 25
        start = self.limit_by_page * (self.page - 1) if self.page > 1 else 0
        end = self.limit_by_page * self.page
        paginated_activities = self.activities[start:end]
        self.available: dict[str, str] = {str(a["id"]): a["name"] for a in paginated_activities}
        self.selected_ids: list[str] = []
        self.selected_tasks: dict[str, object]
        self.selected_names_by_id: dict[str, str] = {}
        self.resultados: dict[str, object] = {"nomes_por_id": {}, "ids": []}

        # Combobox inicial
        self.select = ActivitiesSelect(self.available)
        self.add_item(self.select)

    async def edit_button_state(self, custom_id: str, new_label: str = None, new_disabled: bool = True):
        # Busca o botão pelo custom_id
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.custom_id == custom_id:
                # Edita as propriedades do botão
                if new_label is not None:
                    item.label = new_label
                item.disabled = new_disabled
                break
        else:
            raise ValueError(f"Botão com custom_id '{custom_id}' não encontrado.")


    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Garante que apenas o autor interaja
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Apenas quem iniciou pode interagir com esta view.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Voltar", style=discord.ButtonStyle.success, row=1, custom_id='previous_page', disabled=True)
    async def voltar(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Incrementar a página
        new_page = self.page - 1

        start = self.limit_by_page * (new_page - 1)
        end = self.limit_by_page * new_page
        paginated_activities = self.activities[start:end]

        await self.edit_button_state(custom_id="next_page", new_disabled=False)

        previous_page = new_page -1
        if previous_page < 0:
            button.disabled = True

        start = self.limit_by_page * (previous_page - 1)
        end = self.limit_by_page * previous_page
        previous_paginated_activities = self.activities[start:end]

        if len(previous_paginated_activities) < 1:
            button.disabled = True

        self.page = new_page
        self.available = {str(a["id"]): a["name"] for a in paginated_activities}

        self.select.options = [
            discord.SelectOption(label=self.select._clip(name, self.select.MAX_LABEL), value=act_id)
            for act_id, name in self.available.items()
        ]

        await interaction.response.edit_message(content=self.last_text, view=self)

    @discord.ui.button(label="Avançar", style=discord.ButtonStyle.primary, row=1, custom_id='next_page')
    async def avancar(self, interaction: discord.Interaction, button: discord.ui.Button):

        # Incrementar a página
        new_page = self.page + 1

        start = self.limit_by_page * (new_page - 1)
        end = self.limit_by_page * new_page
        paginated_activities = self.activities[start:end]
        if start > len(self.activities):
            button.disabled = True
            await interaction.response.edit_message(content=self.last_text, view=self)
            return

        next_page = new_page + 1
        start = self.limit_by_page * (next_page - 1)
        end = self.limit_by_page * next_page
        end = end if end < len(self.activities) else len(self.activities)
        next_paginated_activities = self.activities[start:end]
        if len(next_paginated_activities) < 1:
            button.disabled = True

        await self.edit_button_state(custom_id="previous_page", new_disabled=False)

        # Atualiza o seletor com a nova página
        self.page = new_page
        self.available = {str(a["id"]): a["name"] for a in paginated_activities}

        # Atualiza as opções do select com os novos dados
        self.select.options = [
            discord.SelectOption(label=self.select._clip(name, self.select.MAX_LABEL), value=act_id)
            for act_id, name in self.available.items()
        ]

        # Re-renderiza a view
        await interaction.response.edit_message(content=self.last_text, view=self)

    @discord.ui.button(label="Finalizar", style=discord.ButtonStyle.success, row=1)
    async def finalizar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finalizar_interacao(interaction)


    async def finalizar_interacao(self, interaction: discord.Interaction):
        # Salva nas variáveis finais solicitadas
        self.resultados["nomes_por_id"] = dict(self.selected_names_by_id)
        self.resultados["ids"] = list(self.selected_ids)

        # Desabilita itens e remove a view
        for item in self.children:
            item.disabled = True

        text_parts = []
        text_format_runs = []
        cursor = 0

        for project_id, project_data in self.selected_tasks.items():
            project_name = project_data['project_name']

            # adiciona project title
            line = f"{project_name}\n"
            text_parts.append(line)
            text_format_runs.append({
                "startIndex": cursor,
                "format": {"bold": True}
            })
            cursor += len(line)

            # tasks
            for task in project_data['tasks']:
                line = f"- {task['id']} - {task['name']}\n"
                text_parts.append(line)

                text_format_runs.append({
                    "startIndex": cursor,
                    "format": {
                        "link": {"uri": get_secret('TEAMWORK_BASE_URL')+task['id']},   # aqui vc coloca o link da task
                        "bold": False
                    }
                })
                cursor += len(line)

        text = "".join(text_parts)

        # Mostra o resultado ao usuário
        await interaction.response.edit_message(
            content=(
                alter_cell_text(name=self.planning_name, text=text, text_format_runs=text_format_runs, weekday=self.day_value)
            ),
            view=None
        )
