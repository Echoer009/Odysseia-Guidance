# -*- coding: utf-8 -*-
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from .views.base_view import BaseTableView
    from .views.community_members_view import CommunityMembersView
    from .views.general_knowledge_view import GeneralKnowledgeView
    from .views.work_events_view import WorkEventsView
    from .views.vector_db_view import VectorDBView

    AnyDBView: TypeAlias = (
        BaseTableView
        | CommunityMembersView
        | GeneralKnowledgeView
        | WorkEventsView
        | VectorDBView
    )
else:
    AnyDBView = object
