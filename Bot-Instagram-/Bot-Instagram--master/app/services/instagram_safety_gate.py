from __future__ import annotations
import json, threading
from datetime import datetime, timezone
from pathlib import Path
from app.services.instagram_config_runtime_service import InstagramConfigRuntimeService

class InstagramSafetyGate:
    _lock=threading.RLock()
    def __init__(self, campaign_type: str, path: str|None=None):
        self.campaign_type=campaign_type
        self.path=Path(path or Path(__file__).resolve().parents[2]/'data'/'instagram_safety_ledger.json')
        self.path.parent.mkdir(parents=True,exist_ok=True)
    def _load(self):
        try:return json.loads(self.path.read_text(encoding='utf8'))
        except Exception:return {}
    def _save(self,x):
        tmp=self.path.with_suffix('.tmp'); tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8'); tmp.replace(self.path)
    def allow(self, action: str, account_key: str='', commit: bool=True) -> tuple[bool,str]:
        limits=InstagramConfigRuntimeService.limits(self.campaign_type)
        now=datetime.now(timezone.utc); day=now.strftime('%Y-%m-%d'); week=now.strftime('%G-W%V')
        mapping={'comment':'new_intro_comments_max','follow':'follows_max','like':'likes_loves_max','auto_reply':'auto_replies_limit'}
        limit=limits.get(mapping.get(action,''))
        with self._lock:
            data=self._load(); d=data.setdefault(day,{}); count=int(d.get(action,0))
            if isinstance(limit,int) and count>=limit:return False,f'daily_limit:{action}:{limit}'
            if action=='comment' and account_key:
                lifetime=data.setdefault('_lifetime_comments',{})
                absolute_rules=InstagramConfigRuntimeService.safety(self.campaign_type).get('absolute_rules') or {}
                lifetime_max=absolute_rules.get('intro_comment_per_account_lifetime_max')
                if isinstance(lifetime_max, int) and lifetime.get(str(account_key),0)>=lifetime_max:
                    return False,f'account_lifetime_comment_limit:{lifetime_max}'
            if action=='like' and account_key:
                weekly=data.setdefault('_weekly_likes_by_account',{})
                account_week=weekly.setdefault(str(account_key),{})
                week_count=int(account_week.get(week,0))
                absolute_rules=InstagramConfigRuntimeService.safety(self.campaign_type).get('absolute_rules') or {}
                weekly_max=absolute_rules.get('likes_or_loves_per_account_per_week_max')
                if isinstance(weekly_max,int) and week_count>=weekly_max:
                    return False,f'account_weekly_like_limit:{weekly_max}'
            if commit:
                d[action]=count+1
                if action=='comment' and account_key:
                    lifetime=data.setdefault('_lifetime_comments',{})
                    lifetime[str(account_key)]=int(lifetime.get(str(account_key),0))+1
                if action=='like' and account_key:
                    weekly=data.setdefault('_weekly_likes_by_account',{})
                    account_week=weekly.setdefault(str(account_key),{})
                    account_week[week]=int(account_week.get(week,0))+1
                self._save(data)
        return True,'allowed'
