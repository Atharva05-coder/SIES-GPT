interface HeaderProps {
  onMenuClick: () => void;
}

function Header({ onMenuClick }: HeaderProps) {
  return (
    <header className="header">

      <div className="header-left">

        <button
          className="mobile-menu-button"
          onClick={onMenuClick}
        >
          ☰
        </button>

        <div>
          <div className="header-title">
            SIES GPT
          </div>

          <div className="header-subtitle">
            Knowledge Assistant for SIES GST
          </div>
        </div>

      </div>

      <div className="header-right">

        <button className="header-icon-button">
          👤
        </button>

      </div>

    </header>
  );
}

export default Header;