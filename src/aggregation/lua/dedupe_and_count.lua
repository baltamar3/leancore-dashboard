-- Deduplica por event_id e incrementa el contador del bucket en una sola
-- operacion atomica: no hay ventana de carrera entre "ya lo vi" y "lo conte".
--
-- KEYS[1] = dedupe:payments:{event_id}
-- KEYS[2] = metrics:payments:{bucket}
-- ARGV[1] = TTL de la llave de dedupe, en segundos
-- ARGV[2] = campo del hash a incrementar ("processed" | "failed")
-- ARGV[3] = TTL (deslizante) del bucket, en segundos
--
-- Devuelve 1 si se aplico (primera vez que se ve este event_id),
-- 0 si ya se habia visto (no-op, evento duplicado).
if redis.call('SET', KEYS[1], '1', 'NX', 'EX', ARGV[1]) then
    redis.call('HINCRBY', KEYS[2], ARGV[2], 1)
    redis.call('EXPIRE', KEYS[2], ARGV[3])
    return 1
else
    return 0
end
