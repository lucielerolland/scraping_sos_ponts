from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import re, time, json, os
import pandas as pd
from datetime import date
from collections import defaultdict

# Une fonction pour s'authentifier : comment gérer les secrets ?


def authentication(driver, url_authentication):

    driver.get(url_authentication)
    with open("/home/lucie/.config/sos-ponts/config.json", 'r') as f:   # TODO ~
        credentials = json.loads(f.read())

    driver.find_element(By.ID, "id_login").send_keys(credentials['username'])
    driver.find_element(By.ID, "id_password").send_keys(credentials['password'])

    driver.find_element(By.ID, "id_remember").click()
    driver.find_element(By.CLASS_NAME, "custom-login-button").click()

    return


def lit_les_ressource(driver, url_ressources):
    driver.get(url_ressources)

    nombre_ressources = re.findall('[0-9]+', driver.find_element(By.XPATH, "//h1/span").text)[0]

    assert int(nombre_ressources) == len(driver.find_elements(By.CLASS_NAME, "col-xxl-3"))   # On  s'assure que toutes les col-xxl-3 sont des ressources

    ressources = {}

    for ix in range(len(driver.find_elements(By.CLASS_NAME, "col-xxl-3"))):
        time.sleep(1)
        element = driver.find_elements(By.CLASS_NAME, "col-xxl-3")[ix]
        element_name = element.find_element(By.TAG_NAME, 'a').text
        element_url = element.find_element(By.TAG_NAME, 'a').get_attribute('href')
        driver.get(element_url)
        element_modifie = driver.find_element(By.XPATH, "//div[@id='resource-details']/div/span/em").text
        # print(driver.find_element(By.XPATH, '//div[@id = "resource-main"]/div[@class = "text-justified font-marianne"]').text)
        sous_page = driver.find_element(By.XPATH, '//div[@id = "resource-main"]/div[@class = "text-justified font-marianne"]').get_attribute('innerHTML')

        assert element_name not in ressources.keys()  # Pas de doublons dans les noms

        ressources[element_name] = {
            "date_modification": element_modifie,
            "contenu": sous_page,
            "url": element_url,
            }

        driver.get(url_ressources)

        time.sleep(1)

    return ressources


def lit_la_liste_des_taches(driver):

    driver.find_element(By.PARTIAL_LINK_TEXT, "Export CSV").click()   # TODO lire en mémoire directement

    file_path = f'urbanvitaliz-projects-{date.today().strftime("%Y-%m-%d")}.csv'
    export = pd.read_csv(file_path, usecols = ['statut_conseil', 'lien_projet', 'departement'])

    os.remove(file_path)

    return export


def lit_une_tache(driver, url_tache, lire_recommandations):

    driver.get(url_tache)
    time.sleep(1)

    xpath_contexte = "//h6[contains(text(), 'Contexte')]/ancestor::div/following-sibling::div/article"
    contexte = driver.find_element(By.XPATH, xpath_contexte).text

    xpath_complements = "//h6[contains(text(), 'Compléments')]/ancestor::div/following-sibling::div/article"
    complements = driver.find_element(By.XPATH, xpath_complements).text

    tache = {'id': url_tache, 'contexte': contexte, 'complements': complements}

    if lire_recommandations:
        driver.find_element(By.ID, "overview-step-2").click()
        time.sleep(1)
        recommandations = [recommandation.text for recommandation in driver.find_elements(By.XPATH, "//h6")]
        tache['recommandations'] = recommandations

    return tache


# Une fonction pour aller siphonner les tâches à traiter / en attente / en cours (test set en lien avec le métier) vs
# traitées (train & validation)


def lit_les_taches(driver, url_taches):

    driver.get(url_taches)

    # La liste des url des tâches par état est disponible dans un csv dans le site.
    # L'acquérir semble plus robuste que scraper les tâches une à une à cause du slider

    taches = defaultdict(list)

    liste_des_taches = lit_la_liste_des_taches(driver)

    for ix, tache in liste_des_taches.iterrows():
        tache_extraite = lit_une_tache(driver, tache['lien_projet'], tache['statut_conseil'] == "DONE")
        tache_extraite['departement'] = tache['departement']
        taches[tache['statut_conseil']].append(tache_extraite)

    return taches

# Consolider les recommandations présentes dans les taches avec les fiches


def consolider_recommandations(ressources, taches):

    taches_ressources_url = taches.copy()
    taches_ressources_url['DONE'] = list()  # On réécrit les tâches effectuées pour inclure les url des ressources

    for entry in taches['DONE']:
        entry['ressources_url'] = list()
        for ressource in entry["recommandations"]:
            if ressource in ressources.keys():
                entry['ressources_url'].append(ressources[ressource]['url'])

        taches_ressources_url['DONE'].append(entry)

    with open('ressources.json', 'w') as f:
        f.write(json.dumps(ressources))

    with open('taches.json', 'w') as f:
        f.write(json.dumps(taches_ressources_url))

    return taches_ressources_url


# Sauvegarder le tout

if __name__ == '__main__':
    url_base = 'https://sosponts.recoconseil.fr'
    url_authentication = f'{url_base}/accounts/login/'
    url_ressources = f'{url_base}/ressource/'
    url_taches = f'{url_base}/projects/staff/'

    webdriver_service = Service('~/Documents/SOS Ponts/scraping_sos_ponts/geckodriver')

    options = webdriver.FirefoxOptions()
    options.headless = True
    options.set_preference("browser.download.folderList", 2)
    options.set_preference("browser.download.manager.showWhenStarting", False)
    options.set_preference("browser.download.dir", os.getcwd())
    options.set_preference("browser.helperApps.neverAsk.saveToDisk", "text/csv")

    driver = webdriver.Firefox(service=webdriver_service, options=options)

    sos_ponts = driver.get(url_base)

    driver.find_element(By.XPATH, "//button[@title='Refuser tous les cookies']").click()  # On commence par refuser les cookies
    authentication(driver, url_authentication)
    ressources = lit_les_ressource(driver, url_ressources)
    taches = lit_les_taches(driver, url_taches)
    ressources_taches = consolider_recommandations(ressources, taches)
    print('haha')
