import { NavLink } from 'react-router-dom';
import ThemeToggle from '../components/shared/ThemeToggle';
import styles from './HubHeader.module.css';
const NAV = [['Programs', '/programs'], ['Cases', '/cases'], ['Sources', '/sources'], ['Gates', '/gates'], ['Integrations', '/integrations']];
export default function HubHeader() {
 return <header className={styles.header}>
  <NavLink to="/programs" className={styles.brandBlock}><div className={styles.mark} aria-hidden="true">PR</div><div><div className={styles.brand}>THEHUB</div><div className={styles.brandSub}>PRII FEDERATION CONTROL PLANE</div></div></NavLink>
  <nav className={styles.nav} aria-label="Quick navigation">{NAV.map(([label,path]) => <NavLink key={path} to={path} className={({isActive}) => `${styles.navLink} ${isActive ? styles.active : ''}`}>{label}</NavLink>)}</nav>
  <div className={styles.headerTools}><ThemeToggle /></div>
 </header>;
}
