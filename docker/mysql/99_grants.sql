-- Chỉ dùng khi chạy MySQL bằng Docker. Mật khẩu phải khớp DB_PASSWORD trong .env
CREATE USER IF NOT EXISTS 'troly'@'%' IDENTIFIED BY 'doi_mat_khau';
GRANT ALL PRIVILEGES ON qlsv.* TO 'troly'@'%';
GRANT ALL PRIVILEGES ON assistant.* TO 'troly'@'%';
FLUSH PRIVILEGES;
