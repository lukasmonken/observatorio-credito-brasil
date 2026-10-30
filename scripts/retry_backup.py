"""Repete operações de cópia e conferência após falhas temporárias do Drive."""

import argparse
import logging
import random
import re
import shutil
import subprocess
import time

logger = logging.getLogger(__name__)
ATTEMPTS = 3
ATTEMPT_TIMEOUT = 120


def failure_reason(output):
    text = output.lower()
    # Uma falha permanente prevalece mesmo se outra transferência teve timeout.
    permanent = {
        "autorização": ("invalid_grant", "invalid_client", "unauthorized", "insufficientpermissions", "access denied", "permission denied"),
        "armazenamento": ("storagequotaexceeded", "no space left", "dailylimitexceeded"),
        "integridade": ("corrupted", "hashes differ", "sizes differ", "immutable", "files differ", "differences found"),
        "configuração": ("didn't find section", "unknown flag", "config file not found"),
    }
    for reason, markers in permanent.items():
        if any(marker in text for marker in markers):
            return reason, False
    if ("ratelimitexceeded" in text or "too many requests" in text
            or ("quota exceeded" in text and "per minute" in text)
            or re.search(r"\b(?:error|status(?: code)?)[: ]+429\b", text)):
        return "limite temporário de requisições", True
    if re.search(r"\b(?:error|status(?: code)?)[: ]+(?:500|502|503|504)\b", text):
        return "indisponibilidade do serviço", True
    if any(marker in text for marker in (
        "i/o timeout", "connection timed out", "context deadline exceeded",
        "connection reset", "temporary failure in name resolution", "tls handshake timeout",
    )):
        return "falha temporária de conexão", True
    return "erro não classificado; conferir configuração e integridade", False


def run_rclone(arguments):
    if not arguments or arguments[0] not in {"copy", "check"}:
        raise ValueError("Somente copy e check podem receber novas tentativas")
    binary = shutil.which("rclone")
    if binary is None:
        raise RuntimeError("rclone não instalado")
    command = [binary, *arguments, "--retries", "1", "--low-level-retries", "2",
               "--contimeout", "30s", "--timeout", "1m"]
    for attempt in range(1, ATTEMPTS + 1):
        logger.info("rclone %s: tentativa %s/%s", arguments[0], attempt, ATTEMPTS)
        try:
            result = subprocess.run(  # noqa: S603
                command, capture_output=True, text=True, timeout=ATTEMPT_TIMEOUT,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0:
                logger.info("Operação concluída e aprovada pelo rclone")
                return
            reason, retryable = failure_reason(result.stdout + "\n" + result.stderr)
        except subprocess.TimeoutExpired:
            reason, retryable = "limite de tempo da tentativa", True
        # Não publica stderr bruto: respostas OAuth podem conter credenciais.
        if not retryable or attempt == ATTEMPTS:
            raise RuntimeError(f"Backup interrompido após {attempt} tentativa(s): {reason}")
        delay = 30 * (2 ** (attempt - 1)) + random.uniform(0, 10)  # noqa: S311
        logger.warning("%s; nova tentativa em %.1f segundos", reason, delay)
        time.sleep(delay)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        run_rclone(args.arguments)
    except (RuntimeError, ValueError, OSError) as error:
        logger.error("%s", error)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
