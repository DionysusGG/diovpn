import paramiko
import logging
from config import SSH_HOST, SSH_USER, SSH_KEY_PATH, XRAY_MANAGER_PATH

class XraySSHError(Exception):
    pass

def _run_ssh_command(command_args):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(SSH_HOST, username=SSH_USER, key_filename=SSH_KEY_PATH)
        cmd = f"python3 {XRAY_MANAGER_PATH} {' '.join(str(arg) for arg in command_args)}"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        result = out + (f"\n[Ошибка]\n{err}" if err else "")
        return result
    except Exception as e:
        return f"[SSH error] {e}"
    finally:
        ssh.close()
def reset_all_remote():
    return _run_ssh_command(["reset_all"])

def create_vless_key(uuid, days, telegram_id):
    """Создает VLESS ключ на сервере
    
    Args:
        uuid (str): UUID для нового ключа
        days (int): Количество дней действия ключа
        telegram_id (int): Telegram ID пользователя
        
    Returns:
        str: Результат операции
        
    Raises:
        XraySSHError: Если возникла ошибка при создании ключа
    """
    result = _run_ssh_command(["create", uuid, days, telegram_id])
    if "[SSH error]" in result or "[Ошибка]" in result:
        logging.error(f"Failed to create key for user {telegram_id}: {result}")
        raise XraySSHError(f"Failed to create key: {result}")
    logging.info(f"Successfully created key for user {telegram_id} for {days} days")
    return result

def extend_vless_key(uuid, days):
    return _run_ssh_command(["extend", uuid, days])

def revoke_vless_key(uuid):
    return _run_ssh_command(["revoke", uuid])

async def remove_vless_key(uuid):
    """Асинхронная версия revoke_vless_key"""
    import asyncio
    return await asyncio.to_thread(revoke_vless_key, uuid)

async def cleanup_expired_keys():
    """Проверяет и удаляет просроченные ключи"""
    import logging
    from database.db import _get_db
    from datetime import datetime
    
    logging.info("Starting cleanup of expired keys")
    
    with _get_db() as conn:
        # Получаем все просроченные ключи
        expired_keys = conn.execute("""
            SELECT telegram_id, uuid, expires_at 
            FROM keys 
            WHERE expires_at < datetime('now')
        """).fetchall()
        
        if not expired_keys:
            logging.info("No expired keys found")
            return
            
        logging.info(f"Found {len(expired_keys)} expired keys")
        
        for user_id, uuid, expires_at in expired_keys:
            try:
                # Удаляем ключ на сервере
                result = revoke_vless_key(uuid)
                logging.info(f"Revoked key {uuid} for user {user_id}, result: {result}")
                
                # Удаляем ключ из базы
                conn.execute("DELETE FROM keys WHERE uuid = ?", (uuid,))
                logging.info(f"Deleted key {uuid} from database")
                
            except Exception as e:
                logging.error(f"Error cleaning up key {uuid}: {e}")
                continue

async def setup_cleanup_task(dp):
    """Настраивает периодическую задачу очистки ключей"""
    import asyncio
    
    async def periodic_cleanup():
        while True:
            await cleanup_expired_keys()
            # Проверяем каждый час
            await asyncio.sleep(3600)
    
    # Запускаем задачу очистки
    asyncio.create_task(periodic_cleanup())
