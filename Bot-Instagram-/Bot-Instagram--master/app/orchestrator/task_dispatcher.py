import json
import random

from typing import Any, Callable, Dict, List, Optional, Tuple

from app.core.interfaces import IBrowser, IAIAPI, IAccountAPI
from app.tasks.instagram_follow_and_engage_task import InstagramFollowAndEngageTask
from app.tasks.interact_with_instagram_followers import InteractWithInstagramFollowersTask
from app.tasks.notifications_task import InstagramNotificationsTask
from app.tasks.owner_tagged_posts_task import OwnerTaggedPostsTask
from app.tasks.share_instagram_story_task import ShareInstagramStoryTask
from app.tasks.share_instagram_post_task import ShareInstagramPostTask
from app.tasks.instagram_followback import InstagramFollowbackTask
from app.tasks.interact_with_owner_latest_post_task import InteractWithOwnerLatestPostTask
from app.tasks.interact_with_own_posts_task import InteractWithOwnPostsTask
from app.tasks.interact_with_instagram_unread_messages_task import InteractWithInstagramUnreadMessagesTask
from app.tasks.instagram_prospect_discovery_task import InstagramProspectDiscoveryTask
from app.tasks.instagram_prospect_comment_task import InstagramProspectCommentTask
from app.tasks.instagram_prospect_reply_monitor_task import InstagramProspectReplyMonitorTask
from app.tasks.instagram_prospect_no_response_task import InstagramProspectNoResponseTask
from app.tasks.share_instagram_followback_post_task import ShareInstagramFollowbackPostTask
from app.tasks.share_instagram_curated_post_task import ShareInstagramCuratedPostTask
from app.tasks.instagram_campaign_service_content_task import InstagramCampaignServiceContentTask

TASK_REGISTRY = {
    1: {
        "name": "interact_with_owner_latest_post",
        "class": InteractWithOwnerLatestPostTask,
        "enabled": True,
    },
    2: {
        "name": "notifications",
        "class": InstagramNotificationsTask,
        "enabled": True,
    },
    3: {
        "name": "interact_with_instagram_followers",
        "class": InteractWithInstagramFollowersTask,
        "enabled": True,
    },
    4: {
        "name": "share_instagram_story",
        "class": ShareInstagramStoryTask,
        "enabled": True,
    },
    5: {
        "name": "share_instagram_post",
        "class": ShareInstagramPostTask,
        "enabled": True,
    },
    6: {
        "name": "instagram_followback",
        "class": InstagramFollowbackTask,
        "enabled": True,
    },
    7: {
        "name": "owner_tagged_posts",
        "class": OwnerTaggedPostsTask,
        "enabled": True,
    },
    8: {
        "name": "interact_with_own_posts",
        "class": InteractWithOwnPostsTask,
        "enabled": True,
    },
    9: {
        "name": "interact_with_instagram_unread_messages",
        "class": InteractWithInstagramUnreadMessagesTask,
        "enabled": True,
    },
    10: {
        "name": "instagram_prospect_discovery",
        "class": InstagramProspectDiscoveryTask,
        "enabled": True,
    },
    11: {
        "name": "instagram_prospect_comment",
        "class": InstagramProspectCommentTask,
        "enabled": True,
    },
    12: {
        "name": "instagram_prospect_reply_monitor",
        "class": InstagramProspectReplyMonitorTask,
        "enabled": True,
    },
    13: {
        "name": "share_instagram_followback_post",
        "class": ShareInstagramFollowbackPostTask,
        "enabled": True,
    },
    14: {
        "name": "share_instagram_curated_post",
        "class": ShareInstagramCuratedPostTask,
        "enabled": True,
    },
    15: {
        "name": "instagram_campaign_service_content",
        "class": InstagramCampaignServiceContentTask,
        "enabled": True,
    },
    16: {
        "name": "instagram_prospect_no_response",
        "class": InstagramProspectNoResponseTask,
        "enabled": True,
    }
}


def build_task_instance(
    task_id: int,
    *,
    browser: IBrowser,
    ai_api: IAIAPI,
    account_api: IAccountAPI,
    data: dict,
    **kwargs,
) -> Optional[Any]:
    """
    Factory que instancia la clase de la tarea inyectando solo las dependencias necesarias.
    Retorna None si la tarea no existe, está deshabilitada o no pudo instanciarse.
    """
    meta = TASK_REGISTRY.get(task_id)
    if meta is None or not meta.get("enabled", True):
        return None

    task_cls = meta.get("class")
    if task_cls is None:
        return None

    if task_cls == InstagramFollowAndEngageTask:
        return InstagramFollowAndEngageTask(
            browser=browser,
            ai_api=ai_api,
            account_api=account_api,
            data=data,
        )

    if task_cls == InteractWithInstagramFollowersTask:
        return InteractWithInstagramFollowersTask(
            browser=browser,
            ai_api=ai_api,
            account_api=account_api,
            data=data,
        )

    if task_cls == InstagramNotificationsTask:
        return InstagramNotificationsTask(browser=browser)

    if task_cls == ShareInstagramStoryTask:
        return ShareInstagramStoryTask(
            browser=browser,
            ai_api=ai_api,
            account_api=account_api,
            data=data,
        )

    try:
        return task_cls(
            browser=browser,
            ai_api=ai_api,
            account_api=account_api,
            data=data,
            **kwargs,
        )
    except TypeError:
        try:
            return task_cls(
                browser=browser,
                ai_api=ai_api,
                account_api=account_api,
                data=data,
            )
        except TypeError:
            try:
                return task_cls(
                    browser=browser,
                    ai_api=ai_api,
                    data=data,
                )
            except TypeError:
                try:
                    return task_cls(
                        browser=browser,
                        data=data,
                    )
                except TypeError:
                    try:
                        return task_cls(browser=browser)
                    except TypeError:
                        return None


def _wrap_task_execute(task_instance: Any) -> Callable[[Any, Any, Any], Any]:
    """
    Crea un callable compatible con el formato antiguo `(func, arg, arg2, arg3)`.
    El wrapper ignora los parámetros extra y ejecuta `task_instance.execute()`.
    """
    def _call(arg, arg2=None, arg3=None):
        return task_instance.execute()

    return _call


def parse_task_ids(task: Optional[object]) -> Optional[List[int]]:
    """
    Normaliza `task` a lista de ints o None.

    Acepta:
    - list[int]
    - string JSON como "[1,2,3]"
    """
    if task is None:
        return None

    if isinstance(task, str):
        task = task.strip()
        if not task:
            return None
        try:
            parsed = json.loads(task)
        except Exception:
            return None
        task = parsed

    if not isinstance(task, list):
        return None

    out: List[int] = []
    for x in task:
        try:
            out.append(int(x))
        except Exception:
            out.append(-1)

    return out


def build_default_flujos(
    controller: Any,
    *,
    browser: IBrowser,
    ai_api: IAIAPI,
    account_api: IAccountAPI,
    data: dict,
) -> List[Tuple[Any, Any, Any, Any]]:
    """
    Construye la lista mezclada de flujos.

    Formato de salida:
    (
        funcion_ejecutable,
        instancia_o_controller,
        nombre_tarea,
        task_id
    )
    """
    flujos: List[Tuple[Any, Any, Any, Any]] = []

    for task_id in sorted(TASK_REGISTRY.keys()):
        meta = TASK_REGISTRY[task_id]

        if not meta.get("enabled", True):
            continue

        if "class" in meta and meta["class"] is not None:
            task_inst = build_task_instance(
                task_id,
                browser=browser,
                ai_api=ai_api,
                account_api=account_api,
                data=data,
            )
            if task_inst is None:
                continue

            flujos.append(
                (
                    _wrap_task_execute(task_inst),
                    task_inst,
                    meta.get("name"),
                    task_id,
                )
            )

        elif "func" in meta:
            flujos.append(
                (
                    meta["func"],
                    controller,
                    meta.get("name"),
                    task_id,
                )
            )

    random.shuffle(flujos)
    return flujos


def build_selected_flujos(
    controller: Any,
    task_ids: List[int],
    *,
    browser: IBrowser,
    ai_api: IAIAPI,
    account_api: IAccountAPI,
    data: dict,
    force_add_grups_last: bool = True,
) -> Tuple[List[Tuple[Any, Any, Any, Any]], List[Dict[str, Any]], int]:
    """
    Construye flujos según `task_ids` respetando el orden del array.

    Retorna:
    (
        flujos,
        resultados_previos,
        errores_previos
    )
    """
    flujos: List[Tuple[Any, Any, Any, Any]] = []
    resultados_previos: List[Dict[str, Any]] = []
    errores_previos = 0

    for tid in task_ids:
        meta = TASK_REGISTRY.get(tid)

        if meta is None:
            errores_previos += 1
            resultados_previos.append(
                {
                    "task_id": tid,
                    "funcion": None,
                    "error_message": "TASK_ID_INVALIDO: no existe en TASK_REGISTRY",
                }
            )
            continue

        if not meta.get("enabled", True):
            errores_previos += 1
            resultados_previos.append(
                {
                    "task_id": tid,
                    "funcion": meta.get("name"),
                    "error_message": "TASK_DESHABILITADA: enabled=False en TASK_REGISTRY",
                }
            )
            continue

        if "class" in meta and meta["class"] is not None:
            task_inst = build_task_instance(
                tid,
                browser=browser,
                ai_api=ai_api,
                account_api=account_api,
                data=data,
            )

            if task_inst is None:
                errores_previos += 1
                resultados_previos.append(
                    {
                        "task_id": tid,
                        "funcion": meta.get("name"),
                        "error_message": "NO_PUDO_INSTANTIAR: revisar factory",
                    }
                )
                continue

            flujos.append(
                (
                    _wrap_task_execute(task_inst),
                    task_inst,
                    meta.get("name"),
                    tid,
                )
            )

        elif "func" in meta:
            flujos.append(
                (
                    meta["func"],
                    controller,
                    meta.get("name"),
                    tid,
                )
            )

    if force_add_grups_last and flujos:
        pass

    return flujos, resultados_previos, errores_previos