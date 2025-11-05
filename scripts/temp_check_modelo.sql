-- Script para verificar e atualizar modelo pós-2023
SELECT titulo, modelo_texto 
FROM categoricas.c_modelos_texto 
WHERE titulo LIKE '%pós-2023%';
